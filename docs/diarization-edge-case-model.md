"""
Week 08 (28-09-2026 - 04-10-2026)
Task: Adjust data model to handle diarization edge cases

Why this matters:
The data model must preserve the uncertainty and revisions identified in Week
7, otherwise later graph and RAG components will make irreversible claims from
provisional transcript output. This revision provides a stable provenance
foundation for extraction and cross-session linking work.

What this script does:
This design note defines revision-aware transcript, speaker-attribution, and
derived-record fields, including overlap and invalidation rules.
"""

# Week 8 — diarization-aware data model

## Canonical transcript segment

```json
{
  "segment_id": "uuid",
  "session_id": "uuid",
  "sequence": 42,
  "revision": 2,
  "is_final": true,
  "supersedes_revision": 1,
  "start_ms": 84120,
  "end_ms": 90680,
  "text": "Priya will prepare the deployment checklist by Friday.",
  "asr_confidence": 0.91,
  "language": "en",
  "ingest_status": "complete"
}
```

The `(segment_id, revision)` pair identifies immutable evidence. The current
view of a segment is its highest accepted revision; previous revisions remain
auditable and are never overwritten.

## Speaker attribution model

Speaker attribution is stored separately because a label can be corrected
without changing transcript text.

```json
{
  "attribution_id": "uuid",
  "segment_id": "uuid",
  "segment_revision": 2,
  "speaker_label": "SPEAKER_01",
  "speaker_confidence": 0.84,
  "resolved_person_id": null,
  "resolution_status": "unresolved",
  "overlaps_attribution_ids": []
}
```

`resolved_person_id` is optional and can only be set by an evidence-backed
resolution process. `SPEAKER_01` is session-local, not a global person key.

## Derived records and provenance

Summaries, decisions, action items, entity candidates, embeddings, and graph
relationships use the same provenance shape:

```json
{
  "record_id": "uuid",
  "record_type": "action_item",
  "status": "active",
  "confidence": 0.86,
  "evidence": [
    {"segment_id": "uuid", "revision": 2, "start_ms": 84120, "end_ms": 90680}
  ]
}
```

If any cited revision is superseded materially, a dependent record becomes
`needs_review` until its producer re-evaluates it. The earlier record is kept
with `status: superseded`; it is not silently edited.

## Edge-case handling

| Case | Stored representation | Retrieval behavior |
| --- | --- | --- |
| Overlapping speakers | Separate attributions linked through `overlaps_attribution_ids` | Cite each supporting segment/interval |
| Unknown speaker | `speaker_label: UNKNOWN`, null person ID | Do not assign person-based graph edge |
| Low confidence text/label | Numeric confidence plus source/provider metadata when available | Down-rank or flag; do not suppress evidence automatically |
| Missing audio sequence | `ingest_status: gap_detected` on session/range | Warn that answer may be incomplete |
| Corrected transcript | New immutable revision and dependent-record invalidation | Retrieve current evidence; retain history for audit |

## Schema simplification decision

This model adds only two core concepts beyond the Week 2 envelope: immutable
segment revisions and separate speaker attributions. Both can be represented
in PostgreSQL tables without introducing a graph database dependency, which is
straightforward to explain and test.

## WEEK OUTPUT CONTRACT

**Input:** `transcript.segment` events, including any revision or diarization
metadata produced by the ASR module.

**Output:** Revision-aware segment records, separate speaker attributions, and
evidence references usable by storage, graph, and RAG modules.

## Integration status

The Week 8 integration runner validates the model independently and confirms
that the current Dev schema preserves transcript revisions. It reports a
partial result because speaker-attribution and derived-record migrations still
need to be implemented in the production storage layer.
