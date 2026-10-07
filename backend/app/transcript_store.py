"""In-memory transcript ingestion store used until the database endpoint work."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

@dataclass(frozen=True)
class StoredTranscriptEvent:
    """Acknowledgement retained so duplicate deliveries are idempotent."""

    event_id: str
    session_id: str
    segment_id: str
    revision: int


class StaleTranscriptRevisionError(Exception):
    """Raised when a new delivery does not advance a segment revision."""

    def __init__(self, latest_revision: int) -> None:
        self.latest_revision = latest_revision
        super().__init__(f"latest accepted revision is {latest_revision}")


class TranscriptStore:
    """Accept ordered transcript revisions without yet depending on a database."""

    def __init__(self) -> None:
        self._events: dict[str, StoredTranscriptEvent] = {}
        self._latest_revisions: dict[tuple[str, str], int] = {}
        self._lock = Lock()

    def accept(
        self, *, event_id: str, session_id: str, segment_id: str, revision: int
    ) -> tuple[StoredTranscriptEvent, bool]:
        """Return the acknowledgement and whether this call accepted new input.

        The same event ID is acknowledged again without creating a duplicate.
        A new event may only advance a session-local segment revision.
        """
        with self._lock:
            existing = self._events.get(event_id)
            if existing is not None:
                return existing, False

            segment_key = (session_id, segment_id)
            latest_revision = self._latest_revisions.get(segment_key)
            if latest_revision is not None and revision <= latest_revision:
                raise StaleTranscriptRevisionError(latest_revision)

            accepted = StoredTranscriptEvent(
                event_id=event_id,
                session_id=session_id,
                segment_id=segment_id,
                revision=revision,
            )
            self._events[event_id] = accepted
            self._latest_revisions[segment_key] = revision
            return accepted, True

    def clear(self) -> None:
        """Clear temporary state; used by isolated API tests only."""
        with self._lock:
            self._events.clear()
            self._latest_revisions.clear()


transcript_store = TranscriptStore()
