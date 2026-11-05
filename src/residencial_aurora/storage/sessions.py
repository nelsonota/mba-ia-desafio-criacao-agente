"""Repositório SQLite para sessões de API, eventos e pendências."""

from __future__ import annotations

import json
from typing import Any

from residencial_aurora.storage.database import connect, transaction


def get_session(session_id: str) -> dict[str, str] | None:
    with connect() as connection:
        row = connection.execute(
            "SELECT session_id, apartamento, adk_session_id FROM api_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else None


def create_session(session_id: str, apartment: str, adk_session_id: str) -> None:
    with connect() as connection, transaction(connection):
        connection.execute(
            "INSERT INTO api_sessions(session_id, apartamento, adk_session_id) VALUES (?, ?, ?)",
            (session_id, apartment, adk_session_id),
        )


def list_pending_confirmations(session_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT id, action, details_json FROM pending_confirmations "
            "WHERE session_id = ? AND status = 'pending' ORDER BY created_at, id",
            (session_id,),
        ).fetchall()
    confirmations: list[dict[str, Any]] = []
    for row in rows:
        details = json.loads(row["details_json"])
        details.pop("apartamento", None)
        confirmations.append({"id": row["id"], "acao": row["action"], "detalhes": details})
    return confirmations


def append_event(session_id: str, event: dict[str, Any]) -> int:
    event_json = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    with connect() as connection, transaction(connection):
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM session_events WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO session_events(session_id, sequence, event_json) VALUES (?, ?, ?)",
            (session_id, sequence, event_json),
        )
    return int(sequence)


def list_events(session_id: str) -> list[dict[str, Any]]:
    with connect() as connection:
        rows = connection.execute(
            "SELECT sequence, event_json, created_at FROM session_events "
            "WHERE session_id = ? ORDER BY sequence",
            (session_id,),
        ).fetchall()
    return [
        {"sequence": row["sequence"], "event": json.loads(row["event_json"]), "created_at": row["created_at"]}
        for row in rows
    ]
