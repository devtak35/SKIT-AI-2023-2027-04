"""
Week 03 (24-08-2026 - 30-08-2026)
Task: Design the initial database schema

Why this matters:
The FastAPI skeleton from Week 02 needs a stable persistence model before
transcript ingestion and retrieval endpoints are built. This schema preserves
session ownership, transcript revisions, summary provenance, extracted records,
and ordered domain events so Harsh's graph/RAG work can consume durable IDs.

What this script does:
Documents and validates the initial relational schema in
backend/app/schema.sql. The local bootstrap uses SQLite for deterministic CI
tests while keeping application-generated text IDs and portable constraints
ready for a later PostgreSQL migration.
"""

# Schema implementation: backend/app/schema.sql
# Bootstrap helper: backend/app/database.py
# Verification: backend/tests/test_database.py

## Tables and ownership

- `sessions` owns meeting metadata and processing status.
- `transcript_segments` stores every ASR revision using `(segment_id,
  revision)` as its key; corrections never overwrite history silently.
- `summaries` stores versioned summaries and JSON-encoded
  `source_segment_ids` until PostgreSQL `JSONB` is introduced.
- `extracted_items` stores decisions, topics, people, and action items with
  confidence and evidence IDs.
- `domain_events` provides an idempotency key and ordered session event log for
  future SSE delivery.

The graph and vector index are deliberately not duplicated here. They can
reference these canonical IDs through adapters without taking ownership of
transcript text.

## Week output contract

**Input:** Week 02 FastAPI application and the agreed event fields.

**Output:** A runnable schema bootstrap and relational model that accepts a
session, multiple transcript revisions, summaries, extracted records, and
domain events while enforcing IDs, confidence ranges, statuses, and evidence
relationships at the database boundary.

## Verification

```bash
python -m pytest backend/tests/test_database.py -q
```
