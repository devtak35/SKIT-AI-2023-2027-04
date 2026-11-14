"""Database bootstrap helpers for local application and test deployments.

SQLite provides persistent local application storage and isolated test
connections. PostgreSQL is selected explicitly through ``DATABASE_URL``.
"""

from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


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


def open_database(path: str | Path) -> sqlite3.Connection:
    """Open a persistent SQLite database and apply the current schema."""
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    _migrate_legacy_sqlite_schema(connection, database_path)
    initialize_schema(connection)
    return connection


def _migrate_legacy_sqlite_schema(connection: sqlite3.Connection, database_path: Path) -> None:
    """Upgrade the early unscoped transcript key without losing local data.

    Early databases keyed transcript segments by ``(segment_id, revision)``
    and had child tables that referenced that key. The current contract scopes
    IDs to a session. Rebuild only the affected tables and retain a one-time
    side-by-side backup before changing the file.
    """
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    )}
    if "transcript_segments" not in tables:
        return

    columns = connection.execute("PRAGMA table_info(transcript_segments)").fetchall()
    primary_key = [row["name"] for row in sorted(columns, key=lambda row: row["pk"]) if row["pk"]]
    if primary_key == ["session_id", "segment_id", "revision"]:
        return
    if primary_key != ["segment_id", "revision"]:
        raise RuntimeError(
            "Unsupported SQLite transcript schema. Preserve the database and "
            "migrate it to the session-scoped transcript key before startup."
        )

    if not database_path.with_suffix(database_path.suffix + ".pre-migration.bak").exists():
        backup = sqlite3.connect(str(database_path.with_suffix(database_path.suffix + ".pre-migration.bak")))
        try:
            connection.backup(backup)
        finally:
            backup.close()

    segment_rows = [dict(row) for row in connection.execute("SELECT * FROM transcript_segments")]
    speaker_rows = [dict(row) for row in connection.execute("SELECT * FROM speaker_attributions")] if "speaker_attributions" in tables else []
    graph_evidence_rows = [dict(row) for row in connection.execute("SELECT * FROM graph_evidence")] if "graph_evidence" in tables else []
    derived_evidence_rows = [dict(row) for row in connection.execute("SELECT * FROM derived_record_evidence")] if "derived_record_evidence" in tables else []
    sessions = {row["session_id"] for row in connection.execute("SELECT session_id FROM sessions")}
    session_for_segment = {(row["segment_id"], row["revision"]): row["session_id"] for row in segment_rows}

    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        for table in ("speaker_attributions", "graph_evidence", "derived_record_evidence", "transcript_segments"):
            if table in tables:
                connection.execute(f"DROP TABLE {table}")
        connection.commit()
        initialize_schema(connection)

        for row in segment_rows:
            if row["session_id"] not in sessions:
                continue
            connection.execute(
                """INSERT INTO transcript_segments
                   (session_id, segment_id, revision, is_final, start_ms, end_ms,
                    speaker_id, text, asr_confidence, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                tuple(row[key] for key in ("session_id", "segment_id", "revision", "is_final", "start_ms", "end_ms", "speaker_id", "text", "asr_confidence", "created_at")),
            )
        for row in speaker_rows:
            session_id = row.get("session_id") or session_for_segment.get((row["segment_id"], row["segment_revision"]))
            if session_id in sessions:
                connection.execute(
                    """INSERT INTO speaker_attributions
                       (attribution_id, session_id, segment_id, segment_revision, speaker_label,
                        speaker_confidence, resolved_person_id, resolution_status,
                        overlaps_attribution_ids, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (row["attribution_id"], session_id, row["segment_id"], row["segment_revision"], row["speaker_label"], row.get("speaker_confidence"), row.get("resolved_person_id"), row.get("resolution_status", "unresolved"), row.get("overlaps_attribution_ids", "[]"), row["created_at"]),
                )
        for row in graph_evidence_rows:
            if (row["segment_id"], row["segment_revision"]) in session_for_segment:
                connection.execute(
                    """INSERT INTO graph_evidence
                       (evidence_id, record_type, record_id, session_id, segment_id,
                        segment_revision, start_ms, end_ms)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    tuple(row[key] for key in ("evidence_id", "record_type", "record_id", "session_id", "segment_id", "segment_revision", "start_ms", "end_ms")),
                )
        record_sessions = {row["record_id"]: row["session_id"] for row in connection.execute("SELECT record_id, session_id FROM derived_records")}
        for row in derived_evidence_rows:
            session_id = row.get("session_id") or record_sessions.get(row["record_id"])
            if session_id in sessions and (row["segment_id"], row["segment_revision"]) in session_for_segment:
                connection.execute(
                    """INSERT INTO derived_record_evidence
                       (record_id, session_id, segment_id, segment_revision, start_ms, end_ms)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (row["record_id"], session_id, row["segment_id"], row["segment_revision"], row["start_ms"], row["end_ms"]),
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


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
    """Open configured PostgreSQL or persistent local SQLite storage.

    The API must not silently use an in-memory database: that would make
    successful uploads disappear on restart. Tests that need isolation call
    ``open_fixture_database()`` directly. Local application runs use the
    ignored ``backend/data/app.db`` file unless ``DATABASE_PATH`` overrides it.
    """
    if os.getenv("APP_ENV", "development") != "test":
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
    configured_url = database_url or os.getenv("DATABASE_URL")
    if configured_url:
        return open_postgres_database(configured_url)

    configured_path = os.getenv("DATABASE_PATH")
    local_path = Path(configured_path) if configured_path else Path(__file__).resolve().parents[1] / "data" / "app.db"
    return open_database(local_path)
