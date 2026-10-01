"""
Week 04 (31-08-2026 - 06-09-2026)
Task: Align with team on what APIs each service exposes

Why this matters:
The pipeline can only be integrated when modules agree on payload shape,
versioning, and error behavior. This contract translates the Week 2 boundaries
into practical APIs that can be implemented independently against fixtures.

What this script does:
This design note defines the proposed internal event contracts, public
backend endpoints, validation/error behavior, and compatibility rules that
the four owners can implement independently against fixtures.
"""

# Week 4 — API alignment proposal

## Contract rules

Every internal event is a JSON object with this envelope:

```json
{
  "schema_version": "1.0",
  "event_id": "evt-uuid",
  "session_id": "session-uuid",
  "created_at": "2026-08-31T09:00:00Z",
  "payload": {}
}
```

`event_id` is the idempotency key. A consumer may receive the same event more
than once and must acknowledge it once without duplicating data. Timestamps
are UTC ISO-8601 strings. Unknown fields may be ignored for additive changes;
removed or reinterpreted fields require a new `schema_version`.

## Internal event contract

All internal producers emit the Week 2 JSON envelope. The backend validates
`schema_version` and required identifiers before persistence. Event names and
minimum `payload` fields are:

| Event | Producer | Required payload |
| --- | --- | --- |
| `audio.chunk` | Capture | `chunk_id`, `source`, `sequence`, `captured_at`, `sample_rate_hz`, `channels`, `encoding`, `duration_ms`, `audio_ref` |
| `transcript.segment` | ASR | `segment_id`, `revision`, `is_final`, `start_ms`, `end_ms`, `speaker_id`, `text`, `asr_confidence` |
| `summary.update` | NLP | `summary_id`, `version`, `text`, `source_segment_ids`, `is_final` |
| `extraction.update` | NLP | `items[]: {id, type, text, confidence, evidence_segment_ids}` |
| `graph.linked` | Graph linker | `relationship_id`, `source_id`, `target_id`, `relationship_type`, `evidence_segment_ids`, `confidence` |

`type` for extraction is initially one of `person`, `topic`, `decision`, or
`action_item`. New types require a schema-version change, not an undocumented
string.

### Canonical naming decisions

- `speaker_id` is the canonical stored field. A provider may call it
  `speaker_label`, but the ASR adapter maps that name at the boundary.
- `source_segment_ids` is the canonical stored field for summary provenance.
  Garvit's current prompt/reference shape uses `covered_segment_ids`; Dev's
  ingestion adapter should map it before persistence and reject payloads that
  contain neither field.
- `evidence_segment_ids` is used for extracted items and graph links because
  those records assert claims supported by transcript evidence.
- `audio_ref` is a storage reference, never embedded audio bytes in JSON.

### Example event payloads

```json
{
  "schema_version": "1.0",
  "event_id": "evt-transcript-001",
  "session_id": "session-001",
  "created_at": "2026-08-31T09:00:02Z",
  "payload": {
    "segment_id": "seg-001",
    "revision": 1,
    "is_final": false,
    "start_ms": 0,
    "end_ms": 1800,
    "speaker_id": "speaker-1",
    "text": "Let's review the capture prototype next week.",
    "asr_confidence": 0.97
  }
}
```

```json
{
  "schema_version": "1.0",
  "event_id": "evt-summary-001",
  "session_id": "session-001",
  "created_at": "2026-08-31T09:00:10Z",
  "payload": {
    "summary_id": "summary-001",
    "version": 1,
    "text": "The capture prototype will be reviewed next week.",
    "source_segment_ids": ["seg-001"],
    "is_final": false
  }
}
```

An ASR correction reuses `segment_id` with a higher `revision`; it does not
reuse `event_id`. A summary version similarly increments `version` while
retaining the same `summary_id` for one session summary stream.

## Public backend API proposal

| Method and path | Consumer | Purpose | Response guarantee |
| --- | --- | --- | --- |
| `POST /v1/sessions` | Frontend | Create an upload/live session | Returns `session_id` and initial status |
| `GET /v1/sessions/{session_id}` | Frontend | Fetch session state | Returns transcript, current summary, and processing statuses |
| `GET /v1/sessions/{session_id}/updates` | Frontend | Receive live updates via SSE initially | Ordered events with event IDs; reconnect can resume from `after_event_id` |
| `POST /v1/query` | Frontend | Ask across sessions | Returns cited answer, citations, and evidence status |
| `GET /v1/sessions/{session_id}/records` | Frontend | Display extracted decisions/action items | Returns evidence-linked structured records |

### Endpoint behavior

| Endpoint | Success | Required behavior |
| --- | --- | --- |
| `POST /v1/sessions` | `201` | Creates a session and returns its ID and `status: "created"` |
| `GET /v1/sessions/{id}` | `200` | Returns current state; unknown ID is `404` |
| `GET /v1/sessions/{id}/updates` | `200 text/event-stream` | Emits ordered events; `after_event_id` resumes after the last acknowledged event |
| `POST /v1/query` | `200` | Returns a grounded answer or explicit insufficient evidence |
| `GET /v1/sessions/{id}/records` | `200` | Returns records with evidence IDs and confidence |

The frontend never calls PostgreSQL, the vector index, or the graph directly.
The API owns authentication, validation, pagination, and transport details.

Example query request:

```json
{
  "question": "What did we decide about the deployment date?",
  "session_ids": [],
  "top_k": 8
}
```

Example answer response:

```json
{
  "answer": "The team proposed 6 March, subject to integration testing.",
  "citations": [{"session_id": "...", "segment_id": "...", "start_ms": 184200, "end_ms": 188900, "quote": "..."}],
  "insufficient_evidence": false,
  "retrieval_metadata": {"evidence_count": 2, "query_scope": "all_sessions"}
}
```

SSE messages use the event ID as the SSE `id` and the versioned domain event
as the JSON `data`. This gives the browser a simple reconnect cursor without
coupling the UI to a queue implementation.

## Error contract

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "payload.source_segment_ids contains an unknown segment",
    "fields": [{"path": "payload.source_segment_ids[0]", "reason": "not_found"}],
    "retryable": false
  }
}
```

Use `400` for malformed requests, `404` for unknown resources, `409` for an
older revision or duplicate conflicting ID, `422` for semantically invalid
domain data, and `503` for temporary provider/storage unavailability. A
successful request with no support is still `200` with
`insufficient_evidence: true`; it is not a server error.

## Error and compatibility rules

- Validation failures return a machine-readable error code and field details.
- An unsupported schema version is rejected clearly; consumers must not guess
  how to parse it.
- Temporary upstream unavailability is reported as `processing` or `failed`
  session status, not as an empty successful result.
- `POST /v1/query` returns `insufficient_evidence: true` when retrieval cannot
  support an answer.
- Public endpoints are versioned under `/v1`; internal event versioning is
  independent and explicit in every envelope.
- Consumers compare revisions/versions and ignore stale duplicates after
  recording the event acknowledgement.

## Team confirmation checklist

- Dhruv confirms transcript timing units, speaker-label policy, revision rules,
  and confidence scale.
- Garvit confirms extraction item fields, permissible values, and evidence IDs.
- Dev confirms persistence IDs, event delivery mechanism, endpoint ownership,
  and frontend update transport.
- Harsh confirms graph-link payload and citation fields are sufficient for RAG.

## Sign-off record for the next team sync

| Owner | Confirm | Status |
| --- | --- | --- |
| Dhruv | timing units, `speaker_id`, revision/finality, confidence range | Pending team sync |
| Garvit | extraction types, confidence, evidence IDs, summary field mapping | Pending team sync |
| Dev | persistence IDs, ingestion endpoint, SSE cursor, error envelope | Pending team sync |
| Harsh | graph-link fields and citation shape support grounded RAG | Proposed in this document |

These are proposed contracts until the four owners confirm them. Real provider
payloads must be adapted at the service boundary rather than leaking into
downstream code.

## WEEK OUTPUT CONTRACT

**Input:** Week 2 boundaries and Week 3 diagrams.

**Output:** A versioned internal event proposal and `/v1` frontend-facing API
proposal, including examples, revision/idempotency rules, error behavior, and
a concrete checklist for team sign-off.
