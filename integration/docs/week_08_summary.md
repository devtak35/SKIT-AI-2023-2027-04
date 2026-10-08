# Week 08 Integration Summary

**Result: PARTIAL.** The diarization-aware model preserves immutable segment
revisions, separate anonymous speaker attribution, overlap links, and
derived-record review state. Dev's current schema preserves transcript
revisions, while the additional attribution and derived-record migrations
remain pending.

Run from the repository root:

```bash
python3 weekly/integration/week_08_integration.py
```

Known limitations:

- Speaker-attribution and derived-record tables are not yet implemented in
  Dev's database schema.
- Production invalidation/reprocessing is represented by the `needs_review`
  state but is not yet run by a worker.

