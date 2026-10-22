"""
Week 10 (12-10-2026)
Task: Fix bugs, finalize transcript storage APIs

Why this matters:
Before PostgreSQL and vector storage are added, the transcript API must reject
stale revisions while remaining idempotent for retried event delivery. These
are the two failure modes most likely to corrupt downstream evidence.

What this script does:
It verifies duplicate-event idempotency and stale-revision rejection.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import open_fixture_database
from backend.app.transcript_repository import TranscriptRepository
from backend.app.transcript_store import StaleTranscriptRevisionError


def run_check() -> dict[str, object]:
    repository = TranscriptRepository(open_fixture_database())
    kwargs = dict(session_id="session-week10", created_at="2026-10-12T10:00:00Z", segment_id="turn-week10", revision=1, is_final=True, start_ms=0, end_ms=1000, speaker_id="SPEAKER_00", text="hello", asr_confidence=0.99)
    _, first = repository.accept(event_id="event-week10", **kwargs)
    _, duplicate = repository.accept(event_id="event-week10", **kwargs)
    try:
        repository.accept(event_id="event-week10-new", **kwargs)
    except StaleTranscriptRevisionError:
        stale_rejected = True
    else:
        stale_rejected = False
    assert first and not duplicate and stale_rejected
    return {"first_accept": first, "duplicate_is_idempotent": not duplicate, "stale_rejected": stale_rejected}


if __name__ == "__main__":
    print(f"[PASS] Dev Week 10: {run_check()}")

