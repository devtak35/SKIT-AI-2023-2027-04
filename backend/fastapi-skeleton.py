"""
Week 02 (17-08-2026 - 23-08-2026)
Task: Build the backend skeleton with FastAPI

Why this matters:
The backend is the shared entry point for the frontend and the pipeline services. A minimal running API gives later transcript, storage, and RAG endpoints one stable application to extend without prematurely locking their data models.

What this script does:
Provides a small launcher for the FastAPI app implemented in backend/app/main.py.
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
