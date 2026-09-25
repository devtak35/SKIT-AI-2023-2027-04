# Backend API scaffold

This Week 2 scaffold provides the FastAPI application entry point and a health
route. It intentionally does not connect a database or define transcript
storage endpoints; those are later weekly tasks.

## Run locally

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1` instead. The API is available at
`http://127.0.0.1:8000/health`; interactive API docs are at
`http://127.0.0.1:8000/docs`.

The exact FastAPI version is pinned in `requirements.txt`; update it deliberately
after checking the [official release notes](https://fastapi.tiangolo.com/release-notes/)
and running the project's checks.
