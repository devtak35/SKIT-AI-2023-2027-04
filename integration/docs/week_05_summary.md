# Week 05 Integration Summary

**Result: PARTIAL.** The Sprint 2 architecture sign-off was checked against
the latest available capture, NLP, backend/schema, and shared-fixture
artifacts. The baseline is internally consistent, but Week 5 teammate files
and production providers are not present in this checkout.

Run from the repository root:

```bash
python3 weekly/integration/week_05_integration.py
```

The runner checks the frozen architecture decisions, change-control rules,
Sprint 2 acceptance criteria, available teammate smoke tests, backend schema,
and transcript-to-summary evidence IDs.

Known limitations:

- Dhruv, Garvit, and Dev Week 5 artifacts are unavailable, so the runner uses
  their latest available artifacts.
- ASR, LLM generation, durable storage, graph linking, RAG, and frontend
  delivery remain mocked or scaffolded.
