"""
Week 02 (17-08-2026 - 23-08-2026)
Task: Define service boundaries: capture, ASR, summarization, storage, frontend

Why this matters:
Week 1 chose a modular pipeline, but that design is only practical when each
module has an unambiguous responsibility and input/output boundary. These
boundaries let teammates develop against fixtures now and become the API and
schema contracts defined in later weeks.

What this script does:
This design note assigns responsibilities to the six pipeline services and
defines their hand-offs, ownership, and failure rules.
"""

# Week 2 — service boundaries

## Boundary principle

A service owns one transformation or persistence concern. It may validate an
incoming payload, but it must not silently reinterpret another service's
business data. All messages use a versioned JSON envelope:

```json
{
  "schema_version": "1.0",
  "event_id": "uuid",
  "session_id": "uuid",
  "created_at": "ISO-8601 UTC timestamp",
  "payload": {}
}
```

`session_id` identifies a recording/meeting. `event_id` identifies an
individual delivery and enables idempotent processing.

| Service | Owner | Inputs | Outputs | Responsibility |
| --- | --- | --- | --- | --- |
| Capture | Dhruv | System audio or uploaded media | Audio chunks/media reference | Acquire audio without a visible meeting bot where possible; report source health |
| ASR + diarization | Dhruv | Ordered audio chunks | Transcript-segment events | Produce text, timing, speaker label, confidence, revision/finality state |
| Summarization + extraction | Garvit | Stable transcript segments | Summary-update events | Create rolling summary, decisions, action items, entity candidates, and confidence with evidence references |
| Storage + indexing | Dev | All accepted domain events | Durable records/index status | Persist canonical data, create embeddings, expose records; Postgres is source of truth |
| Knowledge graph | Harsh | Persisted extracted records and evidence | Graph-link events/relationships | Link entities, decisions, and action items across sessions conservatively |
| RAG + frontend API | Harsh / Dev | User query plus stored evidence | Cited answer and live/history views | Retrieve evidence, generate grounded answer, and render or stream user-visible state |

## Required payload ownership

| Payload | Producer | Consumer | Minimum fields |
| --- | --- | --- | --- |
| `audio.chunk` | Capture | ASR | `chunk_id`, `source`, `sequence`, `captured_at`, `sample_rate_hz`, `channels`, `encoding`, `duration_ms`, `audio_ref` |
| `transcript.segment` | ASR | NLP, Storage | `segment_id`, `revision`, `is_final`, `start_ms`, `end_ms`, `speaker_id`, `text`, `asr_confidence` |
| `summary.update` | NLP | Storage, Frontend | `summary_id`, `version`, `text`, `source_segment_ids`, `is_final` |
| `extraction.update` | NLP | Storage, Graph | `items[]` with `item_id`, `type`, `text`, `confidence`, `evidence_segment_ids`, optional `owner` and `due_date` |
| `index.ready` | Storage | RAG | `resource_type`, `resource_id`, `embedding_version` |
| `rag.answer` | RAG | Frontend | `answer`, `citations[]`, `insufficient_evidence`, `retrieval_metadata` |

## Cross-boundary rules

- Transcript revisions are upserts keyed by `segment_id`; only final or stable
  revisions may drive durable action-item/decision state.
- Evidence identifiers must be preserved by every downstream transformation.
- Consumers acknowledge successful handling by `event_id` and must tolerate
  duplicate delivery.
- A failed downstream task is retried or marked failed with an observable
  status; it is never discarded silently.
- The frontend never queries the graph or vector database directly. It uses a
  backend API so storage choices remain replaceable.

The audio event uses the Week 1 capture proposal's `captured_at` and
`audio_ref` names. ASR creates `segment_id` values; downstream modules must
preserve them in `source_segment_ids` and `evidence_segment_ids`. These are
version 1 contract proposals and can be revised together before the first
persisted API payload is locked.

## Deployment boundary for the first sprint

The logical services may initially execute as modules/background tasks within
one FastAPI deployment. Their payloads and interfaces remain independent, so a
queue and separate workers can be introduced if load requires it. This is
easier to explain and operate than starting with six networked microservices.

## WEEK OUTPUT CONTRACT

**Input:** Week 1 architecture baseline and the four team members' stated
responsibilities.

**Output:** The service responsibility table, versioned event envelope, and
six payload hand-offs above. Week 3 diagrams and Week 4 API contracts use
these names and ownership boundaries.
