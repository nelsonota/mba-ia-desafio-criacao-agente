"""Regras de consulta e persistência de autorizações de visitantes."""

from __future__ import annotations

from datetime import date
import json
import uuid

from residencial_aurora.storage.database import connect, transaction


def _valid_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("A data deve usar o formato AAAA-MM-DD.")
    return value


def list_visitors(apartment: str) -> list[dict[str, str]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT nome, data FROM visitor_authorizations "
            "WHERE apartamento = ? ORDER BY data, nome",
            (apartment,),
        ).fetchall()
    return [dict(row) for row in rows]


def request_visitor_authorization(
    apartment: str, session_id: str, name: str, visit_date: str
) -> dict[str, object]:
    visit_date = _valid_date(visit_date)
    clean_name = " ".join(name.split())
    if not clean_name:
        return {"status": "invalid_name", "message": "Informe o nome do visitante."}
    confirmation_id = str(uuid.uuid4())
    details = {"apartamento": apartment, "nome": clean_name, "data": visit_date}
    with connect() as connection, transaction(connection):
        connection.execute(
            "INSERT INTO pending_confirmations(id, session_id, action, details_json) "
            "VALUES (?, ?, 'visitor_authorization', ?)",
            (confirmation_id, session_id, json.dumps(details, ensure_ascii=False)),
        )
    return {"status": "confirmation_required", "confirmation": {"id": confirmation_id, **details}}


def add_visitor_authorization(apartment: str, name: str, visit_date: str) -> str:
    """Persiste uma autorização; chamar apenas pelo serviço de confirmação aprovada."""
    visit_date = _valid_date(visit_date)
    authorization_id = str(uuid.uuid4())
    with connect() as connection, transaction(connection):
        connection.execute(
            "INSERT INTO visitor_authorizations(id, apartamento, nome, data) VALUES (?, ?, ?, ?)",
            (authorization_id, apartment, " ".join(name.split()), visit_date),
        )
    return authorization_id
