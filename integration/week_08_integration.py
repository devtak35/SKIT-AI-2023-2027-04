"""
Week 08 Integration Check

Connects: Harsh's diarization-aware data model, the Week 7 quality scenarios,
Dev's revision-capable persistence schema, and Garvit's evidence contract.
Still mocked: production PostgreSQL deployment and a worker that performs
derived-record invalidation after transcript correction.

Result: PARTIAL — revision storage and provenance tables are validated;
automatic invalidation and production PostgreSQL remain pending.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


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


def check_harsh_model() -> None:
    text = (ROOT / "weekly/harsh/week_08_diarization-edge-case-model.md").read_text(encoding="utf-8")
    required = (
        "## Canonical transcript segment",
        "supersedes_revision",
        "## Speaker attribution model",
        "resolved_person_id",
        "overlaps_attribution_ids",
        "## Derived records and provenance",
        "needs_review",
        "## Edge-case handling",
        "## Schema simplification decision",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise AssertionError(f"Week 8 model note is missing: {missing}")
    print("[PASS] Harsh Week 8: immutable revisions, separate attribution, overlap, and invalidation rules documented")


def build_model() -> dict:
    """Create one normalized model record from a corrected diarized segment."""
    segment = {
        "segment_id": "seg-week8-001",
        "session_id": "session-week8-demo",
        "sequence": 42,
        "revision": 2,
        "is_final": True,
        "supersedes_revision": 1,
        "start_ms": 84120,
        "end_ms": 90680,
        "text": "Priya will prepare the deployment checklist by Friday.",
        "asr_confidence": 0.91,
        "language": "en",
        "ingest_status": "complete",
    }
    attribution = {
        "attribution_id": "attr-week8-001",
        "segment_id": segment["segment_id"],
        "segment_revision": segment["revision"],
        "speaker_label": "SPEAKER_01",
        "speaker_confidence": 0.84,
        "resolved_person_id": None,
        "resolution_status": "unresolved",
        "overlaps_attribution_ids": ["attr-week8-002"],
    }
    derived = {
        "record_id": "action-week8-001",
        "record_type": "action_item",
        "status": "needs_review",
        "confidence": 0.86,
        "evidence": [{
            "segment_id": segment["segment_id"],
            "revision": segment["revision"],
            "start_ms": segment["start_ms"],
            "end_ms": segment["end_ms"],
        }],
    }
    return {"segment": segment, "attribution": attribution, "derived": derived}


def validate_model(model: dict) -> None:
    segment = model["segment"]
    attribution = model["attribution"]
    derived = model["derived"]
    if (segment["segment_id"], segment["revision"]) != (attribution["segment_id"], attribution["segment_revision"]):
        raise AssertionError("speaker attribution does not point to the segment revision")
    if segment["supersedes_revision"] >= segment["revision"]:
        raise AssertionError("superseded revision must be older than current revision")
    if attribution["resolved_person_id"] is not None or attribution["resolution_status"] != "unresolved":
        raise AssertionError("anonymous speaker was resolved without an explicit identity step")
    evidence = derived["evidence"]
    if not evidence or evidence[0]["revision"] != segment["revision"]:
        raise AssertionError("derived record does not cite the current segment revision")
    if derived["status"] != "needs_review":
        raise AssertionError("corrected evidence must invalidate dependent records for review")
    print(f"[PASS] Provenance model: segment revision {segment['revision']} supersedes {segment['supersedes_revision']}; derived record is needs_review")


def check_garvit_contract(model: dict) -> None:
    module = load_module("week_08_garvit", "ml/nlp/week4_prompt_refinement.py")
    failures = module.run_checks()
    if failures:
        raise AssertionError("; ".join(failures))
    prompts = module.load_prompts()
    segment = model["segment"]
    segment_for_nlp = {
        "segment_id": segment["segment_id"],
        "revision": segment["revision"],
        "is_final": segment["is_final"],
        "start_ms": segment["start_ms"],
        "end_ms": segment["end_ms"],
        "speaker_label": model["attribution"]["speaker_label"],
        "text": segment["text"],
        "asr_confidence": segment["asr_confidence"],
    }
    prompts.build_summary_messages([segment_for_nlp])
    prompts.build_extraction_messages([segment_for_nlp])
    print("[PASS] Garvit contract: revised final segment remains consumable with evidence fields")


def check_dev_revision_storage(model: dict) -> None:
    database = load_module("week_08_database", "backend/app/database.py")
    connection = database.open_fixture_database()
    segment = model["segment"]
    now = "2026-10-04T12:00:00Z"
    connection.execute(
        "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
        (segment["session_id"], now, now),
    )
    for revision, is_final, text in (
        (1, 0, "Priya will prepare the deployment check list."),
        (2, 1, segment["text"]),
    ):
        connection.execute(
            """
            INSERT INTO transcript_segments
                (segment_id, session_id, revision, is_final, start_ms, end_ms,
                 speaker_id, text, asr_confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (segment["segment_id"], segment["session_id"], revision, is_final,
             segment["start_ms"], segment["end_ms"], model["attribution"]["speaker_label"],
             text, segment["asr_confidence"], now),
        )
    rows = connection.execute(
        "SELECT revision, is_final, text FROM transcript_segments WHERE segment_id = ? ORDER BY revision",
        (segment["segment_id"],),
    ).fetchall()
    if [(row["revision"], row["is_final"]) for row in rows] != [(1, 0), (2, 1)]:
        raise AssertionError("Dev schema did not preserve both immutable transcript revisions")
    tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if not {"speaker_attributions", "derived_records", "derived_record_evidence"}.issubset(tables):
        raise AssertionError("Dev schema is missing diarization provenance tables")
    print("[PASS] Dev schema: both transcript revisions remain queryable for audit")
    print("[PASS] Dev schema: speaker-attribution and derived-record provenance tables are available")


def main() -> int:
    try:
        check_harsh_model()
        model = build_model()
        validate_model(model)
        check_garvit_contract(model)
        check_dev_revision_storage(model)
    except Exception as error:
        print(f"[FAIL] Week 8 chain: {error}")
        print("Result: FAIL — one or more Week 8 integration checks failed")
        return 1
    print(f"[MOCK MODEL] {json.dumps(model, ensure_ascii=False)}")
    print("Result: PARTIAL — diarization-aware provenance passes; production PostgreSQL and invalidation worker remain pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

