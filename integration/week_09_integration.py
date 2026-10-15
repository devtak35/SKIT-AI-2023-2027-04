"""
Week 09 Integration Check

Connects: Harsh's revised architecture, the Week 8 diarization-aware model,
Dev's persistence schema, and Garvit's evidence-bearing NLP contract.
Still mocked: real Dhruv Week 9 accuracy output, production workers, and
automatic derived-record re-evaluation.

Result: PARTIAL — the revised architecture is consistent with the available
contracts; teammate Week 9 artifacts are not present in this checkout.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def check_architecture_note() -> None:
    text = read("weekly/harsh/week_09_revised-architecture.md")
    required = (
        "## Revised evidence flow",
        "## Revision event flow",
        "## Architecture deltas from Week 8",
        "(segment_id, revision)",
        "## Traceability rules for implementation",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise AssertionError(f"Week 9 architecture note is missing: {missing}")
    diagrams = re.findall(r"```mermaid\n(.*?)```", text, flags=re.DOTALL)
    if len(diagrams) < 2:
        raise AssertionError("Week 9 must retain both flow and sequence diagrams")
    print("[PASS] Harsh Week 9: revised flow, event sequence, deltas, and traceability rules documented")


def check_week8_contract() -> None:
    text = read("weekly/harsh/week_08_diarization-edge-case-model.md")
    for marker in ("supersedes_revision", "speaker_confidence", "needs_review", "overlaps_attribution_ids"):
        if marker not in text:
            raise AssertionError(f"Week 8 contract no longer exposes {marker}")
    print("[PASS] Week 8 hand-off: revision, attribution, overlap, and review fields remain available")


def check_dev_schema() -> None:
    schema = read("backend/app/schema.sql")
    required = (
        "PRIMARY KEY (segment_id, revision)",
        "speaker_attributions",
        "derived_records",
        "derived_record_evidence",
        "domain_events",
    )
    missing = [marker for marker in required if marker not in schema]
    if missing:
        raise AssertionError(f"Dev schema is missing revised-architecture support: {missing}")
    connection = sqlite3.connect(":memory:")
    connection.executescript(schema)
    connection.execute(
        "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
        ("session-w9", "2026-10-11T12:00:00Z", "2026-10-11T12:00:00Z"),
    )
    connection.execute(
        "INSERT INTO transcript_segments(segment_id, session_id, revision, start_ms, end_ms, speaker_id, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("seg-w9", "session-w9", 1, 0, 1000, "SPEAKER_01", "Draft", "2026-10-11T12:00:00Z"),
    )
    connection.execute(
        "INSERT INTO transcript_segments(segment_id, session_id, revision, is_final, start_ms, end_ms, speaker_id, text, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("seg-w9", "session-w9", 2, 1, 0, 1000, "SPEAKER_01", "Final", "2026-10-11T12:00:01Z"),
    )
    revisions = connection.execute(
        "SELECT revision FROM transcript_segments WHERE segment_id = ? ORDER BY revision", ("seg-w9",)
    ).fetchall()
    if [row[0] for row in revisions] != [1, 2]:
        raise AssertionError("schema did not preserve both transcript revisions")
    print("[PASS] Dev schema: immutable transcript revisions are queryable and provenance tables exist")


def check_nlp_evidence_contract() -> None:
    text = read("ml/nlp/week4_prompt_refinement.py")
    for marker in ("evidence_segment_ids", "covered_segment_ids", "is_final"):
        if marker not in text:
            raise AssertionError(f"Garvit contract does not expose {marker}")
    print("[PASS] Garvit contract: summaries and extracted items retain source evidence IDs")


def main() -> int:
    try:
        check_architecture_note()
        check_week8_contract()
        check_dev_schema()
        check_nlp_evidence_contract()
    except Exception as error:
        print(f"[FAIL] Week 9 chain: {error}")
        print("Result: FAIL")
        return 1
    print("[MOCK STATUS] Dhruv Week 9 output and automatic invalidation worker are not present")
    print("Result: PARTIAL — revised architecture is contract-compatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
