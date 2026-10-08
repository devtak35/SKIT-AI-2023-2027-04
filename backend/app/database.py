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
    # FastAPI executes synchronous route handlers in a worker thread.  This
    # fixture connection is guarded by the repository lock, so it can safely
    # be shared by those handlers during local tests.
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection
