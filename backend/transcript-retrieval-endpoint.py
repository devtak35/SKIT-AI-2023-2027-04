"""
Week 07 (21-09-2026 - 27-09-2026)
Task: Build the transcript-retrieval endpoint

Why this matters:
The Week 6 upload boundary accepts revision-aware ASR events, but downstream
summarization and the future frontend need a safe way to read them back. This
endpoint makes the latest corrected transcript the default while retaining an
explicit audit view for graph and RAG evidence work.

What this script does:
Provides a runnable launcher for the FastAPI application that exposes
GET /v1/sessions/{session_id}/transcript-segments.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app  # noqa: E402


def main() -> None:
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()


# WEEK OUTPUT CONTRACT:
# Input: session_id and optional include_revisions boolean.
# Output: ordered latest transcript segments, or immutable history when asked.
