# Week 07 Integration Summary

**Result: PARTIAL.** The transcript-quality gap matrix was checked against
representative revision, uncertain-speaker, and overlap cases. The cases flow
through the current NLP contract and transcript upload boundary, including
acceptance of a current revision and rejection of a stale revision.

Run from the repository root:

```bash
python3 weekly/integration/week_07_integration.py
```

Known limitations:

- No real Dhruv Week 7 transcript-quality fixture or WER/DER measurements are
  available in this checkout.
- Quality metrics from a real ASR/diarization run are not yet available. The
  transcript upload and retrieval endpoints now share a revision-aware SQLite
  fixture database; production PostgreSQL follows in Week 11.

