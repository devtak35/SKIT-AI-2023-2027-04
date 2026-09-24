"""
Week 02 Integration Check

Connects: Harsh service boundaries, Dhruv local audio capture, Garvit prompt templates, and Dev FastAPI skeleton.
Still mocked: Synthetic audio instead of a live microphone, fixture ASR transcript, fixture LLM summary, in-memory storage, graph/RAG, and frontend display.

Result: PARTIAL — capture chunk contract, prompt construction, API health route, and mock downstream handoffs are connected.
"""

from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_weekly_module(module_name: str, relative_path: str):
    module_path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load weekly artifact {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    harsh_doc = ROOT / "weekly/harsh/week_02_service-boundaries.md"
    if not harsh_doc.is_file():
        raise FileNotFoundError(harsh_doc)
    boundary_text = harsh_doc.read_text(encoding="utf-8")
    required_boundary_fields = (
        "`captured_at`",
        "`audio_ref`",
        "`source_segment_ids`",
        "`evidence_segment_ids`",
        "`due_date`",
    )
    missing_boundary_fields = [field for field in required_boundary_fields if field not in boundary_text]
    if missing_boundary_fields:
        raise ValueError(f"Harsh's service boundary is missing shared fields: {missing_boundary_fields}")
    print("[PASS] Harsh boundaries: audio and NLP contract fields align with Week 1 proposals")

    dhruv = load_weekly_module("week_02_dhruv", "weekly/dhruv/week_02_local_audio_capture.py")
    dev = load_weekly_module("week_02_dev", "weekly/dev/week_02_fastapi-skeleton.py")
    garvit = load_weekly_module("week_02_garvit", "weekly/garvit/week_02_prompt-templates.py")

    transcript_fixture = json.loads((ROOT / "fixtures/week_02_transcript.json").read_text(encoding="utf-8"))
    transcript_segments = transcript_fixture["segments"]
    session_id = transcript_fixture["session_id"]

    synthetic_pcm = struct.pack("<32000h", *([0] * 32000))
    with TemporaryDirectory(prefix="week02-audio-") as temp_dir:
        chunks = dhruv.make_audio_chunks(
            synthetic_pcm,
            session_id=session_id,
            chunk_directory=Path(temp_dir) / "audio-chunks",
            captured_at=datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc),
        )
        first_event = chunks[0].to_event()
        print(f"[PASS] Dhruv capture: {len(chunks)} synthetic PCM chunks; first event={json.dumps(first_event['payload'])}")

    messages = garvit.build_summary_messages(transcript_segments)
    if not all(segment["segment_id"] in messages[1]["content"] for segment in transcript_segments):
        raise ValueError("The summary prompt lost transcript segment IDs")
    print(f"[PASS] Garvit prompts: {len(messages)} messages built from {len(transcript_segments)} transcript segments")

    with TestClient(dev.app) as client:
        health_response = client.get("/health")
        if health_response.status_code != 200 or health_response.json().get("status") != "ok":
            raise RuntimeError(f"Backend health request failed: {health_response.status_code}")
        print(f"[PASS] Dev FastAPI: GET /health -> {health_response.json()}")

    summary_fixture = json.loads((ROOT / "fixtures/week_02_summary.json").read_text(encoding="utf-8"))
    in_memory_storage = {session_id: {"segments": transcript_segments, **summary_fixture}}
    stored = in_memory_storage[session_id]
    cited_ids = stored["summary"]["source_segment_ids"]
    available_ids = {segment["segment_id"] for segment in stored["segments"]}
    if not set(cited_ids).issubset(available_ids):
        raise ValueError("Mock summary cites transcript segments that are not stored")
    answer = {
        "answer": stored["summary"]["text"],
        "citations": cited_ids,
        "source": "fixture summary; retrieval and generation are mocked",
    }
    print(f"[MOCK] Storage: saved {len(stored['segments'])} transcript segments and summary in memory")
    print(f"[MOCK] RAG / frontend payload: {json.dumps(answer)}")
    print("Result: PARTIAL — runnable scaffolds connect; microphone, ASR, LLM, durable storage, graph, and production RAG remain future work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
