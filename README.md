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
python3 integration/current_pipeline_check.py
```

Run the API with `uvicorn backend.app.main:app --reload` and the frontend with
`cd frontend && npm install && npm run dev`.

The offline demo uses SQLite and needs no database or API keys. Start the API
and frontend in separate terminals. The frontend uses `VITE_API_URL` for a
non-default API URL.

## Local PostgreSQL and provider setup

For PostgreSQL deployment, set `DATABASE_URL` before starting the API. The
local test and demo path remains SQLite when it is unset.

```bash
export DATABASE_URL='postgresql://user:password@localhost:5432/meeting_summary'
uvicorn backend.app.main:app --reload
```

The API uses PostgreSQL whenever `DATABASE_URL` is set. Otherwise it uses a
persistent SQLite database at `backend/data/app.db`; set `DATABASE_PATH` to
choose another local path. Automated tests use isolated in-memory SQLite
connections explicitly. The default embedding path is deterministic and
offline; live Groq generation and external ASR/diarization providers require
their configured credentials and runtime dependencies.

To transcribe an uploaded audio or video recording, set DEEPGRAM_API_KEY in
the root .env and restart the API. The transcript intake page posts the media
to the versioned session audio route. Deepgram returns timestamped utterances
and speaker labels from the recording's audio track; video frames are not
analyzed. The server removes its temporary media file after processing.
Without the key the endpoint returns HTTP 503 and does not create a transcript.
Upload size defaults to 100 MiB and can be changed with
MAX_MEDIA_UPLOAD_BYTES (MAX_AUDIO_UPLOAD_BYTES remains supported as a legacy
fallback).

## API integration seams

- `POST /v1/transcript-segments` and `GET /v1/sessions/{id}/transcript-segments`
  store and retrieve revisioned ASR evidence.
- `POST /v1/sessions/{id}/audio` accepts multipart audio, invokes configured
  Deepgram transcription/diarization, and stores/indexes the returned evidence.
- `POST /v1/sessions/{id}/summaries` stores a Garvit-produced summary only when
  it names existing source segments; `GET .../summaries/latest` drives the UI.
- `POST /v1/graph/records`, `GET /v1/sessions/{id}/records`, and `POST
  /v1/query` are the graph/RAG seams. The frontend uses only these public APIs.
- `GET /v1/semantic-search` exposes the derived pgvector-compatible index for
  development and retrieval integration checks. The built-in `hashing-v1`
  embedder is deterministic and offline; replace it behind `EmbeddingRepository`
  when a production embedding provider is selected. The Week 13 integration
  check exercises the offline audio → NLP → storage → graph/RAG path.
