"""
Week 05 Integration Check

Connects: Harsh architecture sign-off, Dhruv's latest capture reliability
checks, Garvit's latest prompt-refinement checks, Dev's backend/schema
scaffold, and the shared transcript-to-summary fixture.
Still mocked: real Week 5 teammate artifacts, production ASR, LLM calls,
durable PostgreSQL/vector storage, graph linking, RAG, and the frontend.

Result: PARTIAL — the frozen architecture baseline and available fixture
stages pass; Sprint 2 production integrations are not present yet.
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


def check_harsh_signoff() -> None:
    text = (ROOT / "weekly/harsh/week_05_architecture-signoff.md").read_text(encoding="utf-8")
    required = (
        "## Approved baseline",
        "## Decisions frozen for Sprint 2",
        "PostgreSQL",
        "Mandatory source segment IDs",
        "## Explicit non-goals for Sprint 2",
        "## Change-control rule",
        "## Sprint 2 acceptance criteria",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 5 sign-off is missing: {missing}")
    print("[PASS] Harsh sign-off: baseline, non-goals, change control, and acceptance criteria are locked")


def check_dhruv_latest() -> None:
    module = load_module("week_05_dhruv", "weekly/dhruv/week_04_capture-reliability.py")
    for check in (module.test_microphone_fixture, module.test_platform_fixture, module.test_invalid_pcm_is_rejected):
        check()
    print("[PASS] Dhruv latest available artifact: capture ordering and malformed PCM checks")
    print("[KNOWN LIMITATION] Dhruv Week 5 artifact is not present; using Week 4")


def load_fixture_handoff() -> tuple[list[dict], dict]:
    """Load and normalize the shared fixture at the ASR/NLP boundary."""
    raw_transcript = json.loads(
        (ROOT / "fixtures/week_02_transcript.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (ROOT / "fixtures/week_02_summary.json").read_text(encoding="utf-8")
    )
    transcript = [
        {
            **segment,
            "revision": segment.get("revision", 1),
            "is_final": segment.get("is_final", True),
            "speaker_label": segment.get("speaker_label", segment["speaker_id"]),
        }
        for segment in raw_transcript["segments"]
    ]
    valid_ids = {segment["segment_id"] for segment in transcript}
    cited = set(summary["summary"]["source_segment_ids"])
    if not cited or not cited <= valid_ids:
        raise AssertionError(f"summary evidence IDs do not match transcript IDs: {sorted(cited)}")
    print(f"[MOCK ASR] transcript: {json.dumps(transcript, ensure_ascii=False)}")
    print(f"[MOCK NLP INPUT] {len(transcript)} final segments with {len(cited)} evidence IDs")
    return transcript, summary


def check_garvit_latest(transcript: list[dict]) -> None:
    module = load_module("week_05_garvit", "ml/nlp/week4_prompt_refinement.py")
    failures = module.run_checks()
    if failures:
        raise AssertionError("; ".join(failures))
    prompts = module.load_prompts()
    messages = prompts.build_summary_messages(transcript)
    extraction_messages = prompts.build_extraction_messages(transcript)
    print(f"[PASS] Garvit handoff: built {len(messages)} summary messages and {len(extraction_messages)} extraction messages")
    print("[PASS] Garvit latest available artifact: prompt fields, evidence IDs, and input validation")
    print("[KNOWN LIMITATION] Garvit Week 5 artifact is not present; using Week 4")


def check_dev_latest(transcript: list[dict], summary: dict) -> None:
    launcher = load_module("week_05_dev_launcher", "weekly/dev/fastapi-skeleton.py")
    with TestClient(launcher.app) as client:
        response = client.get("/health")
    if response.status_code != 200 or response.json().get("api_version") != "v1":
        raise AssertionError(f"unexpected health response: {response.status_code} {response.text}")

    database = load_module("week_05_dev_database", "backend/app/database.py")
    connection = database.open_fixture_database()
    tables = {
        row["name"]
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    required = {"sessions", "transcript_segments", "summaries", "extracted_items", "domain_events"}
    if not required <= tables:
        raise AssertionError(f"schema is missing tables: {sorted(required - tables)}")
    session_id = "week-05-fixture-session"
    now = "2026-09-13T12:00:00Z"
    connection.execute(
        "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
        (session_id, now, now),
    )
    for segment in transcript:
        connection.execute(
            """
            INSERT INTO transcript_segments
                (segment_id, session_id, revision, is_final, start_ms, end_ms,
                 speaker_id, text, asr_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (segment["segment_id"], session_id, segment["revision"], int(segment["is_final"]),
             segment["start_ms"], segment["end_ms"], segment["speaker_label"],
             segment["text"], segment.get("asr_confidence"), now),
        )
    summary_payload = summary["summary"]
    connection.execute(
        """
        INSERT INTO summaries
            (summary_id, session_id, version, text, source_segment_ids, is_final, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("summary-week-05", session_id, 1, summary_payload["text"],
         json.dumps(summary_payload["source_segment_ids"]), 1, now),
    )
    connection.commit()
    persisted = connection.execute(
        "SELECT COUNT(*) AS count FROM transcript_segments WHERE session_id = ?",
        (session_id,),
    ).fetchone()["count"]
    if persisted != len(transcript):
        raise AssertionError(f"expected {len(transcript)} persisted segments, got {persisted}")
    print(f"[PASS] Dev handoff: health -> {response.json()}, persisted {persisted} transcript segments and 1 cited summary, tables={len(required)}")
    print("[KNOWN LIMITATION] Dev Week 5 artifact is not present; using the available scaffold/schema")


def main() -> int:
    failures: list[str] = []
    try:
        check_harsh_signoff()
        check_dhruv_latest()
        transcript, summary = load_fixture_handoff()
        check_garvit_latest(transcript)
        check_dev_latest(transcript, summary)
    except Exception as error:
        failures.append(str(error))
        print(f"[FAIL] Week 5 chain: {error}")
    if failures:
        print("Result: FAIL — one or more Week 5 integration checks failed")
        return 1
    print("Result: PARTIAL — Week 5 baseline is integrated against available fixtures; production stages remain mocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
