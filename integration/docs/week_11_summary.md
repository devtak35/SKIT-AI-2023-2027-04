# Week 11 integration summary

The Week 11 offline integration connects all four lanes through their current
contracts: Dhruv's speaker-labelled transcript, Dev's revision-aware storage,
Garvit's cited summary/action-item output, and Harsh's evidence-backed graph
record shape.

Run it from the repository root:

```bash
python weekly/integration/week_11_integration.py
```

Status: **PASS** with deterministic fixtures. Live microphone/ASR,
Pyannote, external LLM calls, PostgreSQL deployment, vector indexing, and the
production frontend remain explicitly mocked or pending.

