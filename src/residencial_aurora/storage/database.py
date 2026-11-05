"""Schema e ciclo de vida do armazenamento SQLite."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from residencial_aurora.config import PROJECT_ROOT, settings

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS apartments (
    numero TEXT PRIMARY KEY,
    morador TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS common_areas (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    taxa NUMERIC NOT NULL CHECK (taxa >= 0)
);

CREATE TABLE IF NOT EXISTS reservation_code_registry (
    codigo TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS reservations (
    codigo TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL REFERENCES apartments(numero),
    area TEXT NOT NULL REFERENCES common_areas(id),
    data TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'cancelled'))
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_reservation_active_area_date
    ON reservations(area, data) WHERE status = 'active';

CREATE TABLE IF NOT EXISTS visitor_authorizations (
    id TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL REFERENCES apartments(numero),
    nome TEXT NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_sessions (
    session_id TEXT PRIMARY KEY,
    apartamento TEXT NOT NULL,
    adk_session_id TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS session_events (
    session_id TEXT NOT NULL REFERENCES api_sessions(session_id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    event_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    PRIMARY KEY (session_id, sequence)
);

CREATE TABLE IF NOT EXISTS pending_confirmations (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES api_sessions(session_id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    details_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'denied')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_pending_session_status
    ON pending_confirmations(session_id, status);
"""


def connect(database_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão com constraints de FK e transações explícitas habilitadas."""
    path = Path(database_path) if database_path is not None else settings.database_path
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=30, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Executa operações atômicas com BEGIN IMMEDIATE para serializar gravações."""
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def initialize_database(database_path: str | Path | None = None) -> None:
    """Cria o schema sem apagar dados operacionais já persistidos."""
    with connect(database_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute(
            "INSERT OR IGNORE INTO reservation_code_registry(codigo) SELECT codigo FROM reservations"
        )


def restore_initial_data(database_path: str | Path | None = None) -> None:
    """Restaura os dados iniciais de domínio sem tocar em sessões, eventos ou pendências."""
    initialize_database(database_path)
    path = Path(database_path) if database_path is not None else settings.database_path
    with connect(path) as connection, transaction(connection):
        apartments = json.loads((PROJECT_ROOT / "dados" / "apartamentos.json").read_text(encoding="utf-8"))
        areas = json.loads((PROJECT_ROOT / "dados" / "areas.json").read_text(encoding="utf-8"))
        reservations = json.loads((PROJECT_ROOT / "dados" / "reservas.json").read_text(encoding="utf-8"))
        visitors = json.loads((PROJECT_ROOT / "dados" / "visitantes.json").read_text(encoding="utf-8"))
        connection.executemany(
            "INSERT OR IGNORE INTO reservation_code_registry(codigo) VALUES (?)",
            [(row["codigo"],) for row in reservations],
        )

        connection.executemany(
            "INSERT INTO apartments(numero, morador) VALUES (?, ?) "
            "ON CONFLICT(numero) DO UPDATE SET morador = excluded.morador",
            [(str(row["numero"]), row["morador"]) for row in apartments],
        )
        connection.executemany(
            "INSERT INTO common_areas(id, nome, taxa) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET nome = excluded.nome, taxa = excluded.taxa",
            [(row["id"], row["nome"], row["taxa"]) for row in areas],
        )

        # Este comando é uma restauração explícita para o estado inicial de domínio.
        # Ele mantém sessões e histórico de conversa separados e inalterados.
        connection.execute("DELETE FROM reservations")
        connection.execute("DELETE FROM visitor_authorizations")
        connection.executemany(
            "INSERT INTO reservations(codigo, apartamento, area, data, status) VALUES (?, ?, ?, ?, 'active')",
            [(row["codigo"], str(row["apartamento"]), row["area"], row["data"]) for row in reservations],
        )
        connection.executemany(
            "INSERT INTO visitor_authorizations(id, apartamento, nome, data) VALUES (?, ?, ?, ?)",
            [
                (f"initial-visitor-{index}", str(row["apartamento"]), row["nome"], row["data"])
                for index, row in enumerate(visitors, start=1)
            ],
        )


def ensure_initial_data(database_path: str | Path | None = None) -> None:
    """Carrega as fontes iniciais somente quando o banco ainda não foi semeado."""
    initialize_database(database_path)
    with connect(database_path) as connection:
        seeded = connection.execute("SELECT 1 FROM apartments LIMIT 1").fetchone()
    if seeded is None:
        restore_initial_data(database_path)
