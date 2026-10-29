"""Portable, provenance-preserving transcript embedding index.

The production schema uses pgvector.  The deterministic hashing embedder and
SQLite representation keep the same segment/revision contract available for
local development and CI without an external model or credentials.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Iterable


EMBEDDING_DIMENSIONS = 1536
EMBEDDING_MODEL = "hashing-v1"
TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HashingEmbedder:
    """Dependency-free, deterministic embedder used until a provider is set.

    It is intentionally a fallback rather than an LLM embedding substitute:
    it makes indexing and retrieval testable offline and can be replaced behind
    this interface without changing stored evidence identifiers.
    """

    model = EMBEDDING_MODEL
    dimensions = EMBEDDING_DIMENSIONS

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in TOKEN_PATTERN.findall(text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[bucket] += 1.0 if digest[4] % 2 else -1.0
        magnitude = math.sqrt(sum(value * value for value in vector))
        return [value / magnitude for value in vector] if magnitude else vector


@dataclass(frozen=True)
class SemanticMatch:
    session_id: str
    segment_id: str
    revision: int
    score: float


class EmbeddingRepository:
    """Index and query transcript revisions without becoming a source of truth."""

    def __init__(self, connection: sqlite3.Connection, embedder: HashingEmbedder | None = None) -> None:
        self._connection = connection
        self._embedder = embedder or HashingEmbedder()
        self._lock = Lock()

    @property
    def _postgres(self) -> bool:
        return self._connection.__class__.__module__.startswith("psycopg")

    def index(self, *, session_id: str, segment_id: str, revision: int, text: str, created_at: str) -> None:
        """Upsert one immutable transcript revision into the derived index."""
        vector = self._embedder.embed(text)
        with self._lock:
            if self._postgres:
                serialized = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
                self._connection.execute(
                    """INSERT INTO transcript_embeddings
                       (session_id, segment_id, segment_revision, embedding, model, created_at)
                       VALUES (%s, %s, %s, %s::vector, %s, %s)
                       ON CONFLICT (session_id, segment_id, segment_revision) DO UPDATE SET
                         embedding = EXCLUDED.embedding, model = EXCLUDED.model,
                         created_at = EXCLUDED.created_at""",
                    (session_id, segment_id, revision, serialized, self._embedder.model, created_at),
                )
            else:
                self._connection.execute(
                    """INSERT INTO transcript_embeddings
                       (session_id, segment_id, segment_revision, embedding, model, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(session_id, segment_id, segment_revision) DO UPDATE SET
                         embedding = excluded.embedding, model = excluded.model,
                         created_at = excluded.created_at""",
                    (session_id, segment_id, revision, json.dumps(vector), self._embedder.model, created_at),
                )

    def search(self, question: str, *, session_ids: Iterable[str] = (), top_k: int = 8) -> list[SemanticMatch]:
        """Return current transcript revisions ranked by cosine similarity."""
        query_vector = self._embedder.embed(question)
        if not any(query_vector):
            return []
        allowed = list(dict.fromkeys(session_ids))
        limit = max(1, min(top_k, 20))
        with self._lock:
            if self._postgres:
                serialized = "[" + ",".join(f"{value:.8f}" for value in query_vector) + "]"
                filters = ""
                parameters: list[object] = [serialized]
                if allowed:
                    filters = " AND segment.session_id = ANY(%s)"
                    parameters.append(allowed)
                parameters.append(limit)
                rows = self._connection.execute(
                    f"""SELECT segment.session_id, embedding.segment_id,
                               embedding.segment_revision, 1 - (embedding.embedding <=> %s::vector) AS score
                        FROM transcript_embeddings AS embedding
                        JOIN transcript_segments AS segment
                          ON segment.session_id = embedding.session_id
                         AND segment.segment_id = embedding.segment_id
                         AND segment.revision = embedding.segment_revision
                        WHERE segment.revision = (
                          SELECT MAX(candidate.revision) FROM transcript_segments AS candidate
                          WHERE candidate.session_id = segment.session_id
                            AND candidate.segment_id = segment.segment_id
                        ){filters}
                        ORDER BY embedding.embedding <=> %s::vector
                        LIMIT %s""",
                    parameters[:1] + parameters[1:-1] + [serialized, parameters[-1]],
                ).fetchall()
                return [SemanticMatch(row["session_id"], row["segment_id"], row["segment_revision"], float(row["score"])) for row in rows]

            placeholders = ", ".join("?" for _ in allowed)
            where = f" AND segment.session_id IN ({placeholders})" if allowed else ""
            rows = self._connection.execute(
                f"""SELECT segment.session_id, embedding.segment_id, embedding.segment_revision, embedding.embedding
                    FROM transcript_embeddings AS embedding
                    JOIN transcript_segments AS segment
                      ON segment.session_id = embedding.session_id
                     AND segment.segment_id = embedding.segment_id
                     AND segment.revision = embedding.segment_revision
                    WHERE segment.revision = (
                      SELECT MAX(candidate.revision) FROM transcript_segments AS candidate
                      WHERE candidate.session_id = segment.session_id
                        AND candidate.segment_id = segment.segment_id
                    ){where}""",
                allowed,
            ).fetchall()
        scored = [
            SemanticMatch(row["session_id"], row["segment_id"], row["segment_revision"], sum(a * b for a, b in zip(query_vector, json.loads(row["embedding"]))))
            for row in rows
        ]
        return sorted(scored, key=lambda item: (-item.score, item.session_id, item.segment_id))[:limit]
