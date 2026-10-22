"""
Week 09 (05-10-2026 - 11-10-2026)
Task: Test endpoints with sample transcript data

Why this matters:
The upload and retrieval endpoints must preserve the same revision-aware
contract that Dhruv emits. This smoke test exercises the repository boundary
with the shared sample shape without needing a running server.

What this script does:
It stores one transcript event and verifies that the latest revision is read back.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.transcript_repository import TranscriptRepository
from backend.app.database import open_fixture_database


def run_check() -> dict[str, object]:
    repository = TranscriptRepository(open_fixture_database())
    repository.accept(event_id="event-week9", session_id="session-week9", created_at="2026-10-11T10:00:00Z", segment_id="turn-week9", revision=1, is_final=True, start_ms=0, end_ms=1000, speaker_id="SPEAKER_00", text="hello", asr_confidence=0.99)
    rows = repository.list_segments("session-week9", include_revisions=False)
    assert len(rows) == 1 and rows[0].text == "hello"
    return rows[0].__dict__


if __name__ == "__main__":
    print(f"[PASS] Dev Week 9: {run_check()}")

