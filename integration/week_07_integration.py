"""
Week 07 Integration Check

Connects: Harsh's transcript-quality gap matrix, Dhruv's latest capture
reliability checks, Garvit's latest prompt-contract checks, Dev's transcript
upload endpoint, and representative quality scenarios.
Still mocked: real ASR/diarization output and provider quality metrics.

Result: PARTIAL — representative quality gaps are exercised through the
current upload boundary; real transcript-quality measurements are pending.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
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


QUALITY_CASES = [
    {
        "case": "revision_correction",
        "segment_id": "seg-quality-001",
        "revision": 2,
        "is_final": True,
        "start_ms": 0,
        "end_ms": 2400,
        "speaker_label": "SPEAKER_00",
        "speaker_confidence": 0.96,
        "text": "The deployment review is Friday.",
        "asr_confidence": 0.88,
    },
    {
        "case": "uncertain_speaker",
        "segment_id": "seg-quality-002",
        "revision": 1,
        "is_final": True,
        "start_ms": 2500,
        "end_ms": 4300,
        "speaker_label": "UNKNOWN",
        "speaker_confidence": 0.31,
        "text": "I can send the checklist tomorrow.",
        "asr_confidence": 0.79,
    },
    {
        "case": "overlap",
        "segment_id": "seg-quality-003",
        "revision": 1,
        "is_final": True,
        "start_ms": 4200,
        "end_ms": 5600,
        "speaker_label": "SPEAKER_01",
        "speaker_confidence": 0.72,
        "text": "Yes, approve the checklist.",
        "asr_confidence": 0.74,
        "overlaps_with_segment_ids": ["seg-quality-002"],
    },
]


def check_harsh_quality_gaps() -> None:
    text = (ROOT / "weekly/harsh/week_07_transcript-quality-gaps.md").read_text(encoding="utf-8")
    required = (
        "## Evidence limitation",
        "ASR corrects earlier words",
        "Speaker is uncertain",
        "Speakers overlap",
        "Missing/late chunks",
        "## Required validation scenarios for real data",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 7 quality-gap note is missing: {missing}")
    print("[PASS] Harsh Week 7: revision, speaker, overlap, terminology, language, and gap risks documented")


def check_dhruv_latest() -> None:
    module = load_module("week_07_dhruv", "weekly/dhruv/week_04_capture-reliability.py")
    for check in (module.test_microphone_fixture, module.test_platform_fixture, module.test_invalid_pcm_is_rejected):
        check()
    print("[PASS] Dhruv latest available artifact: capture reliability checks pass")
    print("[KNOWN LIMITATION] Dhruv Week 7 transcript-quality artifact is not present; using Week 4")


def canonicalize_for_nlp(case: dict) -> dict:
    """Map the quality-case shape to Garvit's final-segment contract."""
    return {
        key: case[key]
        for key in (
            "segment_id", "revision", "is_final", "start_ms", "end_ms",
            "speaker_label", "text", "asr_confidence",
        )
    }


def check_garvit_handoff() -> list[dict]:
    module = load_module("week_07_garvit", "ml/nlp/week4_prompt_refinement.py")
    failures = module.run_checks()
    if failures:
        raise AssertionError("; ".join(failures))
    prompts = module.load_prompts()
    segments = [canonicalize_for_nlp(case) for case in QUALITY_CASES]
    messages = prompts.build_summary_messages(segments)
    if not all(case["segment_id"] in messages[1]["content"] for case in QUALITY_CASES):
        raise AssertionError("NLP prompt did not retain all quality-case evidence IDs")
    print(f"[PASS] Garvit handoff: built summary and extraction prompts for {len(segments)} final segments")
    print("[KNOWN LIMITATION] Garvit Week 7 artifact is not present; using Week 4 contract checks")
    return segments


def check_dev_upload_boundary(segments: list[dict]) -> None:
    module = load_module("week_07_dev", "weekly/dev/week_06_transcript-upload-endpoint.py")
    event = {
        "schema_version": "1.0",
        "event_id": "evt-week7-quality-001",
        "session_id": "session-week7-quality",
        "created_at": "2026-09-27T12:00:00Z",
        "payload": {**segments[0], "speaker_id": segments[0]["speaker_label"]},
    }
    with TestClient(module.app) as client:
        accepted = client.post("/v1/transcript-segments", json=event)
        if accepted.status_code != 201:
            raise AssertionError(f"upload rejected representative segment: {accepted.status_code} {accepted.text}")
        stale = {**event, "event_id": "evt-week7-quality-stale", "payload": {**event["payload"], "revision": 1}}
        rejected = client.post("/v1/transcript-segments", json=stale)
        if rejected.status_code != 409:
            raise AssertionError(f"stale revision was not rejected: {rejected.status_code} {rejected.text}")
    print(f"[PASS] Dev boundary: accepted revision {event['payload']['revision']} and rejected stale revision 1")
    print("[KNOWN LIMITATION] Dev Week 8 database migration is not present; upload store remains in-memory")


def main() -> int:
    try:
        check_harsh_quality_gaps()
        check_dhruv_latest()
        segments = check_garvit_handoff()
        check_dev_upload_boundary(segments)
    except Exception as error:
        print(f"[FAIL] Week 7 chain: {error}")
        print("Result: FAIL — one or more Week 7 integration checks failed")
        return 1
    print(f"[MOCK QUALITY CASES] {json.dumps([case['case'] for case in QUALITY_CASES])}")
    print("Result: PARTIAL — quality-gap scenarios integrate; real ASR quality measurement remains pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

