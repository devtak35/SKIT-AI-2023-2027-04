"""
Week 13 (27-10-2026 - 02-11-2026)
Task: Connect both to the backend

Why this matters:
PostgreSQL and vector search only help the pipeline when transcript ingestion
writes canonical data and its derived index together. This keeps Garvit and
Harsh on one evidence contract.

What this script does:
Records the integrated storage boundary in TranscriptRepository and its public
semantic-search API.
"""

`TranscriptRepository.accept()` persists the transcript event, speaker
attribution, and derived embedding in one transaction. `GET /v1/semantic-search`
returns evidence identifiers only; RAG remains responsible for answer wording.
