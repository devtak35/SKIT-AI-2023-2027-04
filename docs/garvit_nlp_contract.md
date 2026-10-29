# Garvit NLP Output Contract

Contract version: `nlp-output-1.0`  
Producer: `garvit`

## Purpose

`ml.nlp.combined_pipeline.MeetingNlpPipeline` consumes only final, revisioned
transcript segments. It produces a running summary, typed extraction records,
an evidence-backed graph batch, and a small frontend display payload. The NLP
layer is provider-independent: callers inject a JSON generator that receives
the established Week 5 prompt messages.

## Input

Each transcript segment requires `segment_id`, `revision`, `is_final=true`,
`start_ms`, `end_ms`, `speaker_label`, `text`, and `asr_confidence`. Segment
IDs must be unique within one processing call. Anonymous speaker labels remain
session-local and must not be emitted as a named person identity.

## Output and safety rules

- `summary` includes `source_segment_ids`, revision-specific `evidence`, and a
  separate `support` assessment.
- `entities` are limited to `person`, `topic`, and `decision`; `action_items`
  retain nullable owners and original due-date wording.
- `graph_batch` is directly compatible with `POST /v1/graph/records`. Only
  records whose deterministic support status is `accepted` are included.
- `display` is the frontend-safe view: text, due-date wording, owner state,
  lifecycle status, support assessment, and evidence references.
- `support.score` is a deterministic lexical-evidence triage score, not a
  calibrated model probability and not a replacement for human review.

## Cross-team integration

Dhruv supplies final transcript revisions. A later correction must trigger a
fresh NLP run; the output preserves the exact source revision. Harsh's graph
endpoint accepts `graph_batch` as-is and handles source-revision invalidation.

The FastAPI app persists the summary portion through
`POST /v1/sessions/{session_id}/summaries` and exposes the latest version from
`GET /v1/sessions/{session_id}/summaries/latest`. The current API stores the
required evidence IDs and keeps the richer support assessment available in the
producer payload for a later schema extension.
