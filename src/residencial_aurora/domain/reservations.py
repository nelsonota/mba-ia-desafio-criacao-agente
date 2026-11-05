"""Regras de leitura e alteração de reservas."""

from __future__ import annotations

from datetime import date, datetime
import json
import secrets
import sqlite3
import unicodedata
import uuid

from residencial_aurora.storage.database import connect, transaction


def _valid_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        # Gemini pode reproduzir datas no formato brasileiro ao chamar uma tool.
        parsed = datetime.strptime(value, "%d/%m/%Y").date()
    return parsed.isoformat()


def _normalized_area_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    without_accents = "".join(character for character in decomposed if not unicodedata.combining(character))
    return " ".join(without_accents.casefold().replace("-", " ").split())


def _resolve_common_area(connection: sqlite3.Connection, area: str) -> sqlite3.Row | None:
    """Resolve tanto o ID interno quanto o nome exibido da área, sem busca aproximada."""
    direct_match = connection.execute(
        "SELECT id, nome, taxa FROM common_areas WHERE id = ?", (area.strip(),)
    ).fetchone()
    if direct_match is not None:
        return direct_match

    normalized = _normalized_area_name(area)
    rows = connection.execute("SELECT id, nome, taxa FROM common_areas ORDER BY id").fetchall()
    aliases = {
        "quadra": {"quadra de esportes", "quadra esportiva", "quadra poliesportiva"},
    }
    return next(
        (
            row
            for row in rows
            if normalized
            in {
                _normalized_area_name(row["id"]),
                _normalized_area_name(row["nome"]),
                *aliases.get(row["id"], set()),
            }
        ),
        None,
    )


def list_reservations(apartment: str) -> list[dict[str, str]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT r.codigo, r.area, a.nome AS area_nome, r.data "
            "FROM reservations r JOIN common_areas a ON a.id = r.area "
            "WHERE r.apartamento = ? AND r.status = 'active' ORDER BY r.data, r.area",
            (apartment,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_reservations_for_verification(apartment: str) -> list[dict[str, str]]:
    """Formato enxuto do endpoint de inspeção do avaliador."""
    with connect() as connection:
        rows = connection.execute(
            "SELECT codigo, area, data FROM reservations "
            "WHERE apartamento = ? AND status = 'active' ORDER BY data, area",
            (apartment,),
        ).fetchall()
    return [dict(row) for row in rows]


def check_availability(area: str, reservation_date: str) -> dict[str, str | bool]:
    reservation_date = _valid_date(reservation_date)
    with connect() as connection:
        common_area = _resolve_common_area(connection, area)
        if common_area is None:
            return {"error": "Área comum não encontrada."}
        occupied = connection.execute(
            "SELECT 1 FROM reservations WHERE area = ? AND data = ? AND status = 'active'",
            (common_area["id"], reservation_date),
        ).fetchone() is not None
    return {
        "area": common_area["nome"],
        "data": reservation_date,
        "disponibilidade": "ocupada" if occupied else "livre",
        "disponivel": not occupied,
    }


def _new_reservation_code(connection: sqlite3.Connection) -> str:
    # O ledger preserva também códigos cujas linhas foram removidas por restauração.
    while True:
        code = f"RSV-{secrets.token_hex(4).upper()}"
        try:
            connection.execute("INSERT INTO reservation_code_registry(codigo) VALUES (?)", (code,))
            return code
        except sqlite3.IntegrityError:
            continue


def create_paid_reservation(
    apartment: str, session_id: str, area: str, reservation_date: str
) -> dict[str, object]:
    """Cria reserva gratuita ou pendência tarifada, sempre com identidade do servidor."""
    reservation_date = _valid_date(reservation_date)
    with connect() as connection, transaction(connection):
        common_area = _resolve_common_area(connection, area)
        if common_area is None:
            return {"status": "invalid_area", "message": "Área comum não encontrada."}
        if connection.execute(
            "SELECT 1 FROM reservations WHERE area = ? AND data = ? AND status = 'active'",
            (common_area["id"], reservation_date),
        ).fetchone():
            return {"status": "occupied", "message": "A área está ocupada nessa data."}
        if common_area["taxa"] > 0:
            confirmation_id = str(uuid.uuid4())
            details = {
                "apartamento": apartment,
                "area": common_area["id"],
                "area_nome": common_area["nome"],
                "data": reservation_date,
                "taxa": float(common_area["taxa"]),
            }
            connection.execute(
                "INSERT INTO pending_confirmations(id, session_id, action, details_json) "
                "VALUES (?, ?, 'paid_reservation', ?)",
                (confirmation_id, session_id, json.dumps(details, ensure_ascii=False)),
            )
            return {"status": "confirmation_required", "confirmation": {"id": confirmation_id, **details}}
        try:
            code = _new_reservation_code(connection)
            connection.execute(
                "INSERT INTO reservations(codigo, apartamento, area, data, status) "
                "VALUES (?, ?, ?, ?, 'active')",
                    (code, apartment, common_area["id"], reservation_date),
            )
        except sqlite3.IntegrityError:
            occupied = connection.execute(
                "SELECT 1 FROM reservations WHERE area = ? AND data = ? AND status = 'active'",
                (area, reservation_date),
            ).fetchone()
            if occupied is None:
                raise
            connection.execute("DELETE FROM reservation_code_registry WHERE codigo = ?", (code,))
            return {"status": "occupied", "message": "A área está ocupada nessa data."}
        return {"status": "reserved", "codigo": code, "area": common_area["nome"], "data": reservation_date}


def cancel_reservation(apartment: str, area: str, reservation_date: str) -> dict[str, object]:
    reservation_date = _valid_date(reservation_date)
    with connect() as connection, transaction(connection):
        common_area = _resolve_common_area(connection, area)
        if common_area is None:
            return {"status": "not_found", "message": "Não há reserva ativa sua para essa área e data."}
        result = connection.execute(
            "UPDATE reservations SET status = 'cancelled' "
            "WHERE apartamento = ? AND area = ? AND data = ? AND status = 'active'",
            (apartment, common_area["id"], reservation_date),
        )
        if result.rowcount != 1:
            return {"status": "not_found", "message": "Não há reserva ativa sua para essa área e data."}
    return {"status": "cancelled", "message": "Reserva cancelada."}
