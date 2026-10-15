"""Database bootstrap helpers for local fixtures and PostgreSQL deployments.

SQLite remains the deterministic test backend.  PostgreSQL is selected
explicitly through ``DATABASE_URL`` so importing the API never requires a
running database or a PostgreSQL driver during unit tests.
"""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from typing import Any


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
POSTGRES_SCHEMA_PATH = Path(__file__).with_name("schema_postgres.sql")


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


def open_postgres_database(database_url: str | None = None) -> Any:
    """Open and initialise a PostgreSQL connection.

    The import is intentionally lazy: local SQLite tests do not need the
    optional PostgreSQL driver.  The connection is returned in autocommit
    mode after the idempotent schema has been applied.

    ``database_url`` may be passed directly in application code or supplied
    via ``DATABASE_URL``.  A missing URL or driver produces an actionable
    configuration error rather than a low-level import traceback.
    """
    url = database_url or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required to use PostgreSQL; "
            "use open_fixture_database() for isolated tests"
        )

    try:
        import psycopg
    except ImportError as error:  # pragma: no cover - depends on deployment extras
        raise RuntimeError(
            "PostgreSQL support requires psycopg[binary]. "
            "Install backend/requirements.txt before starting the API."
        ) from error

    connection = psycopg.connect(url, autocommit=True)
    with connection.cursor() as cursor:
        cursor.execute(POSTGRES_SCHEMA_PATH.read_text(encoding="utf-8"))
    return connection


def open_configured_database(database_url: str | None = None) -> Any:
    """Open the configured production database, or the local fixture database.

    This keeps the test default safe and deterministic while giving deployment
    environments one simple switch: set ``DATABASE_URL`` to a PostgreSQL URL.
    """
    return open_postgres_database(database_url) if (database_url or os.getenv("DATABASE_URL")) else open_fixture_database()
