"""
Week 04 Integration Check

Connects: Harsh API alignment, Dhruv capture reliability checks, Garvit's
latest prompt-contract checks, and Dev's latest FastAPI scaffold.
Still mocked: real Zoom/Meet SDKs, ASR, LLM calls, durable storage, graph/RAG
services, and frontend transport/rendering.

Result: PARTIAL — proposed API contracts agree with the runnable fixture
outputs and reliability checks in this checkout.
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
    """Load a weekly module even when its filename contains hyphens."""
    path = ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {relative_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def check_harsh_api_contract() -> None:
    path = ROOT / "weekly/harsh/week_04_api-alignment.md"
    text = path.read_text(encoding="utf-8")
    required = (
        "schema_version",
        "event_id",
        "session_id",
        "speaker_id",
        "source_segment_ids",
        "evidence_segment_ids",
        "after_event_id",
        "insufficient_evidence",
        "## Error contract",
        "## Sign-off record for the next team sync",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 4 API note is missing: {missing}")
    print("[PASS] Harsh API alignment: envelope, canonical fields, SSE cursor, and errors documented")


def check_dhruv_reliability() -> None:
    module = load_module("week_04_dhruv", "weekly/dhruv/week_04_capture-reliability.py")
    for check in (module.test_microphone_fixture, module.test_platform_fixture, module.test_invalid_pcm_is_rejected):
        check()
    print("[PASS] Dhruv reliability: microphone/platform ordering, timestamps, files, and malformed PCM checks")


def check_garvit_latest_contract() -> None:
    # Use the reusable evaluator because the latest weekly wrapper has a
    # module-name mismatch; keep that mismatch visible as a known issue.
    module = load_module("week_04_garvit_checks", "ml/nlp/week3_prompt_evaluation.py")
    failures = module.evaluate_fixture()
    if failures:
        raise AssertionError("; ".join(failures))
    wrapper = ROOT / "weekly/garvit/week_03_prompt-tests.py"
    if "from prompt_evaluation import" in wrapper.read_text(encoding="utf-8"):
        print("[KNOWN ISSUE] Garvit Week 3 wrapper imports prompt_evaluation, but the file is week3_prompt_evaluation.py")
    print("[PASS] Garvit latest available contract: extracted items cite known transcript IDs")


def check_dev_latest_backend() -> None:
    module = load_module("week_04_dev", "weekly/dev/fastapi-skeleton.py")
    with TestClient(module.app) as client:
        response = client.get("/health")
    if response.status_code != 200 or response.json().get("api_version") != "v1":
        raise AssertionError(f"unexpected backend health response: {response.status_code} {response.text}")
    print(f"[PASS] Dev latest backend scaffold: GET /health -> {response.json()}")


def check_canonical_fixture_handoff() -> None:
    transcript = json.loads((ROOT / "fixtures/week_02_transcript.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "fixtures/week_02_summary.json").read_text(encoding="utf-8"))
    available_ids = {segment["segment_id"] for segment in transcript["segments"]}
    source_ids = summary["summary"]["source_segment_ids"]
    if not source_ids or not set(source_ids) <= available_ids:
        raise AssertionError("canonical summary source_segment_ids are not valid transcript IDs")
    print(f"[MOCK] Canonical handoff: summary source_segment_ids={source_ids}")


def main() -> int:
    stages = (
        ("Harsh API alignment", check_harsh_api_contract),
        ("Dhruv reliability", check_dhruv_reliability),
        ("Garvit latest contract", check_garvit_latest_contract),
        ("Dev latest backend", check_dev_latest_backend),
        ("Canonical fixture handoff", check_canonical_fixture_handoff),
    )
    failures: list[str] = []
    for name, check in stages:
        try:
            check()
        except Exception as error:  # report every stage so sync is actionable
            failures.append(f"{name}: {error}")
            print(f"[FAIL] {name}: {error}")

    if failures:
        print("Result: FAIL — one or more Week 4 integration checks failed")
        return 1
    print("Result: PARTIAL — aligned fixture checks pass; real APIs, storage, graph, RAG, and frontend remain future work")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
