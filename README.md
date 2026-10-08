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
- `ml/rag/` — Evidence retrieval foundation; knowledge-graph integration is planned
- `fixtures/` — Sample data for testing
- `docs/architecture.md` — System architecture
- `docs/PROGRESS.md` — Weekly progress log

## Run the current offline checks

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
python -m pytest -q
python integration/current_pipeline_check.py
```

Run the API with `uvicorn backend.app.main:app --reload` and the frontend with
`cd frontend && npm install && npm run dev`.
