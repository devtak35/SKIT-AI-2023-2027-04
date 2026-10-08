"""
Week 06 Integration Check

Connects: Harsh's ASR/diarization contract-readiness review, Dhruv's latest
capture reliability checks, Garvit's latest prompt-refinement checks, Dev's
revision-capable schema, and a representative transcript event.
Still mocked: Dhruv's real early ASR/diarization output, production NLP,
PostgreSQL/vector storage, graph/RAG services, and frontend delivery.

Result: PARTIAL — the representative event passes the downstream contract
checks; real ASR/diarization quality cannot be claimed from this checkout.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_module(module_name: str, relative_path: str):
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


MOCK_EVENT = {
    "schema_version": "1.0",
    "event_id": "evt-week6-0001",
    "session_id": "session-week6-demo",
    "created_at": "2026-09-18T10:31:02Z",
    "payload": {
        "segment_id": "seg-week6-0001",
        "revision": 2,
        "is_final": True,
        "start_ms": 84120,
        "end_ms": 90680,
        "speaker_label": "SPEAKER_01",
        "text": "Priya will prepare the deployment checklist by Friday.",
        "asr_confidence": 0.91,
        "speaker_confidence": 0.84,
        "language": "en",
        "overlaps_with_segment_ids": [],
        "source_audio_offset_ms": 84120,
    },
}


def check_harsh_review() -> None:
    text = (ROOT / "weekly/harsh/week_06_asr-diarization-review.md").read_text(encoding="utf-8")
    required = (
        "## Contract review",
        "Speaker label is present",
        "## Diarization-specific findings",
        "speaker_confidence",
        "overlaps_with_segment_ids",
        "## Handoff acceptance checklist",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 6 review is missing: {missing}")
    print("[PASS] Harsh review: timing, revisions, speaker uncertainty, overlap, and handoff gaps documented")


def check_event_shape() -> None:
    event = MOCK_EVENT
    payload = event["payload"]
    if event["schema_version"] != "1.0" or not event["event_id"] or not event["session_id"]:
        raise AssertionError("event envelope is incomplete")
    if payload["revision"] < 1 or payload["start_ms"] >= payload["end_ms"]:
        raise AssertionError("invalid revision or timing")
    if not payload["text"].strip() or not 0 <= payload["asr_confidence"] <= 1:
        raise AssertionError("invalid text or ASR confidence")
    if not payload["speaker_label"] or not 0 <= payload["speaker_confidence"] <= 1:
        raise AssertionError("invalid speaker attribution metadata")
    if payload["overlaps_with_segment_ids"] != []:
        raise AssertionError("mock overlap metadata should be an empty list")
    print(f"[MOCK] Representative event: {payload['segment_id']} revision {payload['revision']} ({payload['start_ms']}–{payload['end_ms']} ms)")


def check_dhruv_latest() -> None:
    module = load_module("week_06_dhruv", "weekly/dhruv/week_04_capture-reliability.py")
    for check in (module.test_microphone_fixture, module.test_platform_fixture, module.test_invalid_pcm_is_rejected):
        check()
    print("[PASS] Dhruv latest available artifact: capture input remains ordered and readable")
    print("[KNOWN LIMITATION] Real Dhruv early ASR/diarization output is absent; event review is representative only")


def canonical_segment() -> dict:
    """Map the Week 6 provider-shaped event to the NLP contract."""
    payload = MOCK_EVENT["payload"]
    return {
        "segment_id": payload["segment_id"],
        "revision": payload["revision"],
        "is_final": payload["is_final"],
        "start_ms": payload["start_ms"],
        "end_ms": payload["end_ms"],
        "speaker_label": payload["speaker_label"],
        "text": payload["text"],
        "asr_confidence": payload["asr_confidence"],
    }


def check_garvit_latest(segment: dict) -> None:
    module = load_module("week_06_garvit", "ml/nlp/week4_prompt_refinement.py")
    failures = module.run_checks()
    if failures:
        raise AssertionError("; ".join(failures))
    prompts = module.load_prompts()
    summary_messages = prompts.build_summary_messages([segment])
    extraction_messages = prompts.build_extraction_messages([segment])
    print(f"[PASS] Garvit handoff: final revision {segment['revision']} accepted by both prompt builders ({len(summary_messages)} + {len(extraction_messages)} messages)")
    print("[PASS] Garvit latest available artifact: provisional input is rejected for durable extraction")


def check_dev_revision_storage(segment: dict) -> None:
    launcher = load_module("week_06_dev_launcher", "weekly/dev/fastapi-skeleton.py")
    with TestClient(launcher.app) as client:
        response = client.get("/health")
    if response.status_code != 200:
        raise AssertionError(f"backend health failed: {response.status_code}")

    database = load_module("week_06_dev_database", "backend/app/database.py")
    connection = database.open_fixture_database()
    connection.execute(
        "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
        (MOCK_EVENT["session_id"], MOCK_EVENT["created_at"], MOCK_EVENT["created_at"]),
    )
    payload = segment
    for revision, is_final, text in ((1, 0, "Priya will prepare the deployment checklist."), (2, 1, payload["text"])):
        connection.execute(
            """
            INSERT INTO transcript_segments
                (segment_id, session_id, revision, is_final, start_ms, end_ms,
                 speaker_id, text, asr_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (payload["segment_id"], MOCK_EVENT["session_id"], revision, is_final,
             payload["start_ms"], payload["end_ms"], payload["speaker_label"],
             text, payload["asr_confidence"], MOCK_EVENT["created_at"]),
        )
    rows = connection.execute(
        "SELECT revision, is_final FROM transcript_segments WHERE segment_id = ? ORDER BY revision",
        (payload["segment_id"],),
    ).fetchall()
    if [(row["revision"], row["is_final"]) for row in rows] != [(1, 0), (2, 1)]:
        raise AssertionError("schema did not preserve provisional and final revisions")
    print("[PASS] Dev schema: representative segment maps speaker_label to speaker_id and preserves revisions 1→2")


def main() -> int:
    failures: list[str] = []
    try:
        check_harsh_review()
        check_event_shape()
        check_dhruv_latest()
        segment = canonical_segment()
        print(f"[CANONICAL TRANSCRIPT] {json.dumps(segment, ensure_ascii=False)}")
        check_garvit_latest(segment)
        check_dev_revision_storage(segment)
    except Exception as error:
        failures.append(str(error))
        print(f"[FAIL] Week 6 chain: {error}")
    if failures:
        print("Result: FAIL — one or more Week 6 integration checks failed")
        return 1
    print("Result: PARTIAL — representative ASR/diarization handoff integrates; real quality review is pending Dhruv output")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
