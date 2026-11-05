"""Persistência SQLite do assistente."""

from residencial_aurora.storage.database import (
    connect,
    ensure_initial_data,
    initialize_database,
    restore_initial_data,
)

__all__ = ["connect", "ensure_initial_data", "initialize_database", "restore_initial_data"]
