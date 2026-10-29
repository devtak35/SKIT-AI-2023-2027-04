"""SQLite-backed transcript persistence used by the Week 7 and 8 APIs."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from threading import Lock

from backend.app.database import open_configured_database, open_fixture_database
from backend.app.embeddings import EmbeddingRepository
from backend.app.transcript_store import StaleTranscriptRevisionError, StoredTranscriptEvent


class SessionNotFoundError(Exception):
    """Raised when retrieval is requested for a session that does not exist."""


class SummaryValidationError(ValueError):
    """Raised when a summary does not cite evidence in its session."""


@dataclass(frozen=True)
class PersistedSegment:
    segment_id: str
    revision: int
    is_final: bool
    start_ms: int
    end_ms: int
    speaker_id: str
    text: str
    asr_confidence: float | None
    created_at: str


@dataclass(frozen=True)
class PersistedSummary:
    summary_id: str
    session_id: str
    version: int
    text: str
    source_segment_ids: list[str]
    is_final: bool
    created_at: str


class TranscriptRepository:
    """Portable persistence boundary for transcript API contracts."""

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._connection = connection or open_fixture_database()
        self._lock = Lock()
        self.embeddings = EmbeddingRepository(self._connection)

    @property
    def _postgres(self) -> bool:
        """Whether this connection is the optional psycopg production backend."""
        return self._connection.__class__.__module__.startswith("psycopg")

    def accept(self, *, event_id: str, session_id: str, created_at: str,
               segment_id: str, revision: int, is_final: bool, start_ms: int,
               end_ms: int, speaker_id: str, text: str,
               asr_confidence: float | None) -> tuple[StoredTranscriptEvent, bool]:
        """Persist an event once and only allow revisions to advance."""
        with self._lock:
            placeholder = "%s" if self._postgres else "?"
            existing = self._connection.execute(
                f"SELECT session_id, payload FROM domain_events WHERE event_id = {placeholder}", (event_id,)
            ).fetchone()
            if existing is not None:
                payload = json.loads(existing["payload"])
                return StoredTranscriptEvent(event_id, existing["session_id"], payload["segment_id"], payload["revision"]), False

            latest = self._connection.execute(
                f"SELECT MAX(revision) AS revision FROM transcript_segments WHERE session_id = {placeholder} AND segment_id = {placeholder}",
                (session_id, segment_id),
            ).fetchone()["revision"]
            if latest is not None and revision <= latest:
                raise StaleTranscriptRevisionError(latest)

            try:
                self._connection.execute("BEGIN") if not self._postgres else None
                self._connection.execute(
                    "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (%s, %s, %s) ON CONFLICT (session_id) DO NOTHING" if self._postgres else "INSERT OR IGNORE INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
                    (session_id, created_at, created_at),
                )
                self._connection.execute(
                    "UPDATE sessions SET status = 'processing', updated_at = %s WHERE session_id = %s" if self._postgres else "UPDATE sessions SET status = 'processing', updated_at = ? WHERE session_id = ?",
                    (created_at, session_id),
                )
                self._connection.execute(
                    """INSERT INTO transcript_segments
                       (segment_id, session_id, revision, is_final, start_ms, end_ms, speaker_id, text, asr_confidence, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""" if self._postgres else """INSERT INTO transcript_segments
                       (segment_id, session_id, revision, is_final, start_ms, end_ms, speaker_id, text, asr_confidence, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (segment_id, session_id, revision, is_final if self._postgres else int(is_final), start_ms, end_ms, speaker_id, text, asr_confidence, created_at),
                )
                self._connection.execute(
                    """INSERT INTO speaker_attributions
                       (attribution_id, session_id, segment_id, segment_revision, speaker_label, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s)""" if self._postgres else """INSERT INTO speaker_attributions
                       (attribution_id, session_id, segment_id, segment_revision, speaker_label, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (f"{session_id}:{segment_id}:r{revision}:primary", session_id, segment_id, revision, speaker_id, created_at),
                )
                self._connection.execute(
                    """INSERT INTO domain_events(event_id, session_id, event_type, schema_version, payload, created_at)
                       VALUES (%s, %s, 'transcript.segment', '1.0', %s::jsonb, %s)""" if self._postgres else """INSERT INTO domain_events(event_id, session_id, event_type, schema_version, payload, created_at)
                       VALUES (?, ?, 'transcript.segment', '1.0', ?, ?)""",
                    (event_id, session_id, json.dumps({"segment_id": segment_id, "revision": revision}), created_at),
                )
                self.embeddings.index(
                    session_id=session_id,
                    segment_id=segment_id,
                    revision=revision,
                    text=text,
                    created_at=created_at,
                )
                # A corrected source revision invalidates derived graph claims
                # that cited an older revision; immutable history is retained.
                self._connection.execute(
                    """UPDATE graph_entities SET status = 'needs_review', updated_at = ?
                       WHERE entity_id IN (
                           SELECT record_id FROM graph_evidence
                           WHERE record_type = 'entity' AND session_id = ? AND segment_id = ? AND segment_revision < ?
                       )""" if not self._postgres else """UPDATE graph_entities SET status = 'needs_review', updated_at = %s
                       WHERE entity_id IN (
                           SELECT record_id FROM graph_evidence
                           WHERE record_type = 'entity' AND session_id = %s AND segment_id = %s AND segment_revision < %s
                       )""",
                    (created_at, session_id, segment_id, revision),
                )
                self._connection.execute(
                    """UPDATE graph_action_items SET status = 'needs_review', updated_at = ?
                       WHERE action_item_id IN (
                           SELECT record_id FROM graph_evidence
                           WHERE record_type = 'action_item' AND session_id = ? AND segment_id = ? AND segment_revision < ?
                       )""" if not self._postgres else """UPDATE graph_action_items SET status = 'needs_review', updated_at = %s
                       WHERE action_item_id IN (
                           SELECT record_id FROM graph_evidence
                           WHERE record_type = 'action_item' AND session_id = %s AND segment_id = %s AND segment_revision < %s
                       )""",
                    (created_at, session_id, segment_id, revision),
                )
                self._connection.commit() if not self._postgres else None
            except Exception:
                self._connection.rollback()
                raise
            return StoredTranscriptEvent(event_id, session_id, segment_id, revision), True

    def list_segments(self, session_id: str, *, include_revisions: bool) -> list[PersistedSegment]:
        with self._lock:
            placeholder = "%s" if self._postgres else "?"
            if self._connection.execute(f"SELECT 1 FROM sessions WHERE session_id = {placeholder}", (session_id,)).fetchone() is None:
                raise SessionNotFoundError(session_id)
            if include_revisions:
                query = f"SELECT * FROM transcript_segments WHERE session_id = {placeholder} ORDER BY start_ms, end_ms, segment_id, revision"
            else:
                query = f"""SELECT segment.* FROM transcript_segments AS segment
                           WHERE segment.session_id = {placeholder} AND segment.revision = (
                               SELECT MAX(candidate.revision) FROM transcript_segments AS candidate
                               WHERE candidate.session_id = segment.session_id AND candidate.segment_id = segment.segment_id
                           ) ORDER BY segment.start_ms, segment.end_ms, segment.segment_id"""
            rows = self._connection.execute(query, (session_id,)).fetchall()
            return [PersistedSegment(row["segment_id"], row["revision"], bool(row["is_final"]), row["start_ms"], row["end_ms"], row["speaker_id"], row["text"], row["asr_confidence"], row["created_at"]) for row in rows]

    def list_session_ids(self) -> list[str]:
        """Return known sessions in stable order for cross-session retrieval."""
        with self._lock:
            rows = self._connection.execute("SELECT session_id FROM sessions ORDER BY created_at, session_id").fetchall()
            return [row["session_id"] for row in rows]

    def list_sessions(self) -> list[dict[str, object]]:
        """Return dashboard metadata without exposing storage internals."""
        with self._lock:
            rows = self._connection.execute(
                """SELECT session_id, title, status, created_at, updated_at,
                          (SELECT COUNT(*) FROM transcript_segments AS segment
                           WHERE segment.session_id = sessions.session_id
                             AND segment.revision = (SELECT MAX(candidate.revision)
                               FROM transcript_segments AS candidate
                               WHERE candidate.session_id = segment.session_id
                                 AND candidate.segment_id = segment.segment_id)) AS segment_count
                   FROM sessions ORDER BY updated_at DESC, session_id"""
            ).fetchall()
            return [dict(row) for row in rows]

    def save_summary(self, *, summary_id: str, session_id: str, version: int,
                     text: str, source_segment_ids: list[str], is_final: bool,
                     created_at: str) -> PersistedSummary:
        """Persist a Garvit-produced, evidence-linked running summary."""
        with self._lock:
            placeholder = "%s" if self._postgres else "?"
            if self._connection.execute(
                f"SELECT 1 FROM sessions WHERE session_id = {placeholder}", (session_id,)
            ).fetchone() is None:
                raise SessionNotFoundError(session_id)
            available = self._connection.execute(
                f"SELECT DISTINCT segment_id FROM transcript_segments WHERE session_id = {placeholder}",
                (session_id,),
            ).fetchall()
            known_ids = {row["segment_id"] for row in available}
            unknown_ids = set(source_segment_ids) - known_ids
            if unknown_ids:
                raise SummaryValidationError(f"summary cites unknown segment IDs: {sorted(unknown_ids)}")
            payload = json.dumps(source_segment_ids)
            if self._postgres:
                self._connection.execute(
                    """INSERT INTO summaries(summary_id, session_id, version, text, source_segment_ids, is_final, created_at)
                       VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                       ON CONFLICT (summary_id, version) DO UPDATE SET
                         text = EXCLUDED.text, source_segment_ids = EXCLUDED.source_segment_ids,
                         is_final = EXCLUDED.is_final, created_at = EXCLUDED.created_at""",
                    (summary_id, session_id, version, text, payload, is_final, created_at),
                )
            else:
                self._connection.execute(
                    """INSERT INTO summaries(summary_id, session_id, version, text, source_segment_ids, is_final, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(summary_id, version) DO UPDATE SET
                         text = excluded.text, source_segment_ids = excluded.source_segment_ids,
                         is_final = excluded.is_final, created_at = excluded.created_at""",
                    (summary_id, session_id, version, text, payload, int(is_final), created_at),
                )
                self._connection.commit()
            return PersistedSummary(summary_id, session_id, version, text, source_segment_ids, is_final, created_at)

    def latest_summary(self, session_id: str) -> PersistedSummary | None:
        with self._lock:
            placeholder = "%s" if self._postgres else "?"
            if self._connection.execute(
                f"SELECT 1 FROM sessions WHERE session_id = {placeholder}", (session_id,)
            ).fetchone() is None:
                raise SessionNotFoundError(session_id)
            row = self._connection.execute(
                f"SELECT * FROM summaries WHERE session_id = {placeholder} ORDER BY created_at DESC, version DESC LIMIT 1",
                (session_id,),
            ).fetchone()
            if row is None:
                return None
            values = row["source_segment_ids"]
            return PersistedSummary(row["summary_id"], row["session_id"], row["version"], row["text"], json.loads(values) if isinstance(values, str) else values, bool(row["is_final"]), str(row["created_at"]))

    def clear(self) -> None:
        """Reset application fixture data; used by isolated API tests."""
        with self._lock:
            for table in ("graph_evidence", "graph_relationships", "graph_action_items", "graph_entities", "derived_record_evidence", "derived_records", "transcript_embeddings", "summaries", "speaker_attributions", "domain_events", "transcript_segments", "sessions"):
                self._connection.execute(f"DELETE FROM {table}")
            self._connection.commit()


transcript_repository = TranscriptRepository(open_configured_database())
