"""
Week 10 Integration Check

Connects: Harsh's Sprint 3 sign-off with the revised architecture, Week 8
provenance model, and Dev/Garvit contract surfaces.
Still mocked: owner confirmations, real provider payloads, and production
re-evaluation/indexing workers.

Result: PARTIAL — Sprint 3 entry criteria pass against repository fixtures;
team-owner confirmation is still an external follow-up.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def check_signoff_note() -> None:
    text = read("weekly/harsh/week_10_sprint3-design-signoff.md")
    required = (
        "## Approved Sprint 3 baseline",
        "## Decision record",
        "## Scope of this sign-off",
        "## Approved implementation constraints",
        "## Sign-off conditions for implementation review",
        "## Sprint 3 entry criteria",
        "## WEEK OUTPUT CONTRACT",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise AssertionError(f"Week 10 sign-off note is missing: {missing}")
    approved_count = len(re.findall(r"\| .* \| Approved \|", text))
    if approved_count < 5:
        raise AssertionError("sign-off record must contain the five approved baseline decisions")
    print("[PASS] Harsh Week 10: Sprint 3 baseline and implementation conditions are signed off")


def check_entry_contracts() -> None:
    week9 = read("weekly/harsh/week_09_revised-architecture.md")
    week8 = read("weekly/harsh/week_08_diarization-edge-case-model.md")
    schema = read("backend/app/schema.sql")
    checks = {
        "architecture cites immutable revisions": "(segment_id, revision)" in week9,
        "model defines review state": "needs_review" in week8,
        "database stores revision key": "PRIMARY KEY (segment_id, revision)" in schema,
        "database stores derived evidence": "derived_record_evidence" in schema,
        "public API version is frozen": "/v1" in read("weekly/harsh/week_04_api-alignment.md"),
    }
    failed = [label for label, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"Sprint 3 entry criteria failed: {failed}")
    for label in checks:
        print(f"[PASS] {label}")


def main() -> int:
    try:
        check_signoff_note()
        check_entry_contracts()
    except Exception as error:
        print(f"[FAIL] Week 10 chain: {error}")
        print("Result: FAIL")
        return 1
    print("[PENDING] Team-owner confirmations and real provider fixture review remain")
    print("Result: PARTIAL — Sprint 3 may begin against the signed-off contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
