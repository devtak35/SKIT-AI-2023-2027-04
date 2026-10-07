# Week 06 Integration Summary

**Result: PARTIAL.** Harsh's ASR/diarization review is integrated with a
representative transcript event, the current capture/NLP checks, and Dev's
revision-capable schema. This validates the handoff shape without claiming
real ASR or diarization quality before Dhruv's early output is available.

Run from the repository root:

```bash
python3 weekly/integration/week_06_integration.py
```

The runner verifies envelope fields, millisecond timing, revision/finality,
speaker confidence, overlap metadata, prompt input handling, and persistence
of provisional revision 1 followed by final revision 2.

Known limitations:

- No real Dhruv Week 6 ASR/diarization fixture is present; the event is
  representative mock data.
- Speaker labels remain session-local and anonymous.
- Production storage, graph/RAG, and frontend stages are not implemented yet.
