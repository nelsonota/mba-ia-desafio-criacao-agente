"""Consumo transacional, durável e de uso único das confirmações."""

from __future__ import annotations

import json
import secrets
import sqlite3

from residencial_aurora.storage.database import connect, transaction


def _new_reservation_code(connection: sqlite3.Connection) -> str:
    while True:
        code = f"RSV-{secrets.token_hex(4).upper()}"
        try:
            connection.execute("INSERT INTO reservation_code_registry(codigo) VALUES (?)", (code,))
            return code
        except sqlite3.IntegrityError:
            continue


def consume_confirmation(
    session_id: str, confirmation_id: str, confirmed: bool
) -> dict[str, object] | None:
    """Consome uma pendência válida e grava evento/efeito de domínio na mesma transação."""
    with connect() as connection, transaction(connection):
        pending = connection.execute(
            "SELECT p.id, p.action, p.details_json, s.apartamento "
            "FROM pending_confirmations p JOIN api_sessions s ON s.session_id = p.session_id "
            "WHERE p.id = ? AND p.session_id = ? AND p.status = 'pending'",
            (confirmation_id, session_id),
        ).fetchone()
        if pending is None:
            return None

        action = pending["action"]
        details = json.loads(pending["details_json"])
        apartment = pending["apartamento"]
        if details.get("apartamento") != apartment:
            raise ValueError("A confirmação não pertence ao apartamento da sessão.")

        if not confirmed:
            result: dict[str, object] = {"status": "denied", "message": "Confirmação negada; nenhuma alteração foi feita."}
            final_status = "denied"
        elif action == "paid_reservation":
            code = _new_reservation_code(connection)
            try:
                connection.execute(
                    "INSERT INTO reservations(codigo, apartamento, area, data, status) "
                    "VALUES (?, ?, ?, ?, 'active')",
                    (code, apartment, details["area"], details["data"]),
                )
            except sqlite3.IntegrityError:
                occupied = connection.execute(
                    "SELECT 1 FROM reservations WHERE area = ? AND data = ? AND status = 'active'",
                    (details["area"], details["data"]),
                ).fetchone()
                if occupied is None:
                    raise
                connection.execute("DELETE FROM reservation_code_registry WHERE codigo = ?", (code,))
                result = {"status": "occupied", "message": "A área ficou ocupada nessa data; a reserva não foi criada."}
                final_status = "approved"
            else:
                result = {
                    "status": "reserved",
                    "codigo": code,
                    "area": details["area_nome"],
                    "data": details["data"],
                }
                final_status = "approved"
        elif action == "visitor_authorization":
            connection.execute(
                "INSERT INTO visitor_authorizations(id, apartamento, nome, data) VALUES (?, ?, ?, ?)",
                (f"visitor-{secrets.token_hex(16)}", apartment, details["nome"], details["data"]),
            )
            result = {"status": "approved", "message": "Visitante autorizado.", "nome": details["nome"], "data": details["data"]}
            final_status = "approved"
        else:
            raise ValueError(f"Ação de confirmação desconhecida: {action}")

        connection.execute(
            "UPDATE pending_confirmations SET status = ? WHERE id = ? AND status = 'pending'",
            (final_status, confirmation_id),
        )
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM session_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        event = {
            "type": "confirmation",
            "confirmation_id": confirmation_id,
            "action": action,
            "confirmed": confirmed,
            "result": result,
        }
        connection.execute(
            "INSERT INTO session_events(session_id, sequence, event_json) VALUES (?, ?, ?)",
            (session_id, sequence, json.dumps(event, ensure_ascii=False, separators=(",", ":"))),
        )
        return result
