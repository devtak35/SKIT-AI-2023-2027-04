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
- `frontend/` — React/Next.js frontend
- `ml/audio/` — ASR + diarization pipeline
- `ml/nlp/` — Summarization + extraction pipeline
- `ml/rag/` — Knowledge graph + RAG query pipeline
- `fixtures/` — Sample data for testing
- `docs/architecture.md` — System architecture
- `docs/PROGRESS.md` — Weekly progress log
