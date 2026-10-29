# AI Realtime Video Summary Generator

Captures live meetings, lectures, and webinars — or recorded video uploads —
and generates a continuously updating summary as it plays, instead of
waiting until the session ends. Keeps a persistent memory across past
sessions via a knowledge graph and retrieval-augmented generation (RAG),
so users can ask natural-language questions about earlier sessions and get
a cited answer.

Final-year B.Tech thesis project — Department of Computer Science &
Engineering, Swami Keshvanand Institute of Technology, Management &
Gramothan, Jaipur.

## Team
- Harsh Vardhan Kharol — Team Lead, Architecture, Knowledge Graph & RAG
- Dhruv Vij — Speech & Audio Processing (ASR, Diarization)
- Garvit Agrawal — NLP (Summarization, Action-Item Extraction)
- Dev Tak — Backend & Frontend

## Structure
- `backend/` — FastAPI backend
- `frontend/` — React/Vite frontend
- `ml/audio/` — ASR + diarization pipeline
- `ml/nlp/` — Summarization + extraction pipeline
- `backend/app/rag.py` — Evidence-grounded retrieval and cited answer generation
- `fixtures/` — Sample data for testing
- `docs/architecture.md` — System architecture
- `docs/PROGRESS.md` — Weekly progress log

## Run the current offline checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
python3 weekly/integration/week_13_integration.py
```

Run the API with `uvicorn backend.app.main:app --reload` and the frontend with
`cd frontend && npm install && npm run dev`.

For a containerized local demo, run `docker compose up --build`. It exposes the
frontend on `http://localhost:5173`, the API on `http://localhost:8000`, and
PostgreSQL only within the compose network. The frontend API base URL is a
build-time setting; set `VITE_API_BASE_URL` to the deployed API URL when
building for a cloud environment.

## Local PostgreSQL and provider setup

Start the pgvector-backed database:

```bash
docker compose up -d postgres
cp .env.example .env
set -a; source .env; set +a
python3 scripts/runtime_check.py
uvicorn backend.app.main:app --reload --env-file .env
```

The API uses PostgreSQL whenever `DATABASE_URL` is set and keeps the in-memory
SQLite fixture for tests when it is absent. `scripts/runtime_check.py` prints
configured provider names without exposing secrets and verifies the PostgreSQL
schema when a database URL is present. The default provider values remain
`fixture` until real ASR, diarization, LLM, and embedding keys are added to
`.env`.

## API integration seams

- `POST /v1/transcript-segments` and `GET /v1/sessions/{id}/transcript-segments`
  store and retrieve revisioned ASR evidence.
- `POST /v1/sessions/{id}/summaries` stores a Garvit-produced summary only when
  it names existing source segments; `GET .../summaries/latest` drives the UI.
- `POST /v1/graph/records`, `GET /v1/sessions/{id}/records`, and `POST
  /v1/query` are the graph/RAG seams. The frontend uses only these public APIs.
- `GET /v1/semantic-search` exposes the derived pgvector-compatible index for
  development and retrieval integration checks. The built-in `hashing-v1`
  embedder is deterministic and offline; replace it behind `EmbeddingRepository`
  when a production embedding provider is selected. The Week 13 integration
  check exercises the offline audio → NLP → storage → graph/RAG path.
