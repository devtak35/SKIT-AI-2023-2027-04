"""Small schema bootstrap helper used by local fixtures and CI tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the initial tables and indexes on an open SQLite connection."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.commit()


def open_fixture_database() -> sqlite3.Connection:
    """Return an in-memory database suitable for deterministic local tests."""
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection
