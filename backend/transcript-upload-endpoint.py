"""
Week 06 (14-09-2026 - 20-09-2026)
Task: Build the transcript-upload API endpoint

Why this matters:
ASR output must cross a stable, validated boundary before summarization,
storage, and RAG can use it. This endpoint applies the Week 4 event contract
and preserves idempotency and revision rules before Week 8 connects it to the
database.

What this script does:
Provides a small runnable launcher for the FastAPI application containing the
`POST /v1/transcript-segments` endpoint implemented in `backend/app/main.py`.
"""

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402


def main() -> None:
    """Run the Week 6 API slice locally for a manual contract check."""
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()


# WEEK OUTPUT CONTRACT:
# Input: a Week 4 transcript.segment JSON envelope with a canonical
#        `speaker_id`, revision, timing, text, and ASR confidence.
# Output: HTTP 201 acknowledgement for accepted or duplicate delivery, HTTP
#         409 for a stale revision, and HTTP 422 for malformed event data.
