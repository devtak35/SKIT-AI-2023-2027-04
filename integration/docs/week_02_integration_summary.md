# Week 02 Integration Summary

**Result: PARTIAL.** The service-boundary proposal, local audio chunk contract, provider-neutral prompt builder, and FastAPI health route are connected in a runnable integration script. Synthetic audio, a fixture transcript, fixture summary, in-memory storage, and a citation-shaped response stand in for hardware and pipeline services that are still being built.

## Member deliverables

| Owner / instruction file(s) | Week 2 work | Status |
|---|---|---|
| Harsh — root `AGENTS.md` | [`weekly/harsh/week_02_service-boundaries.md`](../harsh/week_02_service-boundaries.md) | Service owners, event envelope, payload handoffs, retries, and logical deployment boundary documented |
| Dhruv — `ml/audio/AGENTS.md` | [`weekly/dhruv/week_02_local_audio_capture.py`](../dhruv/week_02_local_audio_capture.py) and [`ml/audio/capture.py`](../../ml/audio/capture.py) | Local microphone capture writes a WAV and timestamped 16 kHz mono PCM chunks |
| Garvit — `ml/nlp/AGENTS.md` | [`weekly/garvit/week_02_prompt-templates.py`](../garvit/week_02_prompt-templates.py) and [`ml/nlp/prompts.py`](../../ml/nlp/prompts.py) | Provider-neutral JSON-output prompts preserve evidence IDs and avoid guessing missing fields |
| Dev — `backend/AGENTS.md` and `frontend/AGENTS.md` | [`weekly/dev/week_02_fastapi-skeleton.py`](../dev/week_02_fastapi-skeleton.py), [`backend/app/main.py`](../../backend/app/main.py) | Minimal FastAPI app and health endpoint; both Dev instruction files specify this same backend task |

## Week 2 handoffs

- **Capture → ASR:** emits a version 1 event envelope with `session_id`, `event_id`, `chunk_id`, source, sequence, capture time, sample rate, channels, encoding, duration, and a local PCM `audio_ref`. The captured WAV is also retained for local playback/debugging.
- **ASR → NLP:** the fixture uses `segment_id`, `speaker_id`, `start_ms`, `end_ms`, and `text`, with an optional ASR confidence. The ASR implementation is still future work.
- **NLP → storage / graph:** prompt output requests summary, decision, and action-item records with source segment IDs and a support confidence. The LLM response is fixture data; the prompt is not sent to a model.
- **Backend:** `GET /health` returns service readiness and API version. Transcript upload/retrieval and durable storage are reserved for later Dev weeks.
- **RAG / UI:** the integration script forms a mock response whose citations point to stored fixture segment IDs. Retrieval, answer generation, graph expansion, and frontend rendering remain unimplemented.

## Verification

Run from the repository root:

```bash
python3 weekly/integration/week_02_integration.py
```

The script imports each runnable Week 2 artifact, creates two seconds of synthetic PCM in a temporary folder, builds a prompt from the transcript fixture, calls `/health` through FastAPI's in-process client, and checks that the mock summary citations refer to stored transcript segments. It does not access a microphone or make an external model call.

## Open dependencies and issues

1. Week 1 research identified bot-free system-loopback needs, while Week 2 implements a microphone input. macOS ScreenCaptureKit, Windows WASAPI, and Linux PipeWire system-output adapters remain platform work; local microphone capture alone does not capture meeting participants reliably.
2. ASR must adopt the Week 2 transcript segment fields and define speaker-label revisions/finality before Garvit can consume real output.
3. The summary schema and meaning/calibration of `confidence` remain provisional; Week 3 prompt testing should evaluate evidence support and field completeness.
4. Backend package versions are pinned in its requirements file, but the current machine's preinstalled FastAPI version differs from that pin. The integration run validates the basic scaffold against the installed package; use a clean virtual environment and install the pinned requirements for a reproducible setup.
5. Dev's backend and frontend instruction files duplicate the same Week 2 FastAPI task and shared `weekly/dev/` destination. One artifact represents that assignment for both files.
