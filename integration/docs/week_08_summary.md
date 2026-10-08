# Week 08 Integration Summary

**Result: PARTIAL.** The diarization-aware model preserves immutable segment
revisions, separate anonymous speaker attribution, overlap links, and
derived-record review state. Dev's current schema preserves transcript
revisions, speaker attribution, and derived-record evidence in the fixture
database.

Run from the repository root:

```bash
python3 weekly/integration/week_08_integration.py
```

Known limitations:

- Production invalidation/reprocessing is represented by the `needs_review`
  state but is not yet run by a worker; production PostgreSQL is planned for
  Week 11.

