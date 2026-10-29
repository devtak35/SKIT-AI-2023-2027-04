# Week 13 integration summary

The Week 13 integration check connects the latest available Dhruv transcript
contract, Garvit's combined NLP output, Dev's transcript/embedding storage, and
Harsh's graph/RAG boundary. It persists the summary and graph batch, then
answers a question using exact revisioned transcript citations.

Run from the repository root:

```bash
python3 weekly/integration/week_13_integration.py
```

Status: **PASS** with deterministic fixtures. No Week 13 Dhruv file exists in
the checkout, so the integration uses Dhruv's latest Week 12 crosstalk contract
and the shared audio fixture. Provider inference, PostgreSQL deployment, and
external answer generation remain mocked.
