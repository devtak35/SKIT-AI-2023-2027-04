"""
Week 08 (28-09-2026 - 04-10-2026)
Task: Connect endpoints to the database

Why this matters:
Weeks 6 and 7 established ingestion and retrieval contracts; they must now
share database state instead of an isolated in-memory upload store. The
revision-preserving database boundary also supplies provenance for future RAG
citations and diarization correction.

What this script does:
Runs the FastAPI application backed by the SQLite-compatible schema. The
repository persists events, transcript revisions, and speaker attribution
atomically; production PostgreSQL can use the same relational contract.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()


# WEEK OUTPUT CONTRACT:
# Input: a validated transcript.segment event or a retrieval request.
# Output: atomically persisted immutable revisions and raw speaker attribution.
