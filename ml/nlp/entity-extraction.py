"""
Week 12 (20-10-2026 - 26-10-2026)
Task: Add NER for entities: people, dates, topics

Why this matters:
The Week 6 summarization pipeline produces typed, evidence-linked extraction
records, but downstream graph ingestion expects a separate entities/actions
batch. This adapter preserves that evidence and captures explicit date mentions
for later schema alignment without guessing a calendar year.

What this script does:
It uses the Week 3 fixture to normalize people/topics/decisions and action
items into the graph payload shape, and extracts explicit date mentions with
their source segment IDs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NLP_DIR = ROOT / "ml" / "nlp"
if str(NLP_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_DIR))

from week12_entity_extraction import normalize_extraction

FIXTURE = NLP_DIR / "fixtures" / "week_03_sample_transcripts.json"


def main() -> int:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    case = cases[0]
    result = normalize_extraction(case["reference_extraction"], case["transcript_segments"])
    assert result["entities"]
    assert result["action_items"]
    assert all(item["evidence_segment_ids"] for item in result["entities"] + result["action_items"])
    assert all(set(mention) == {"text", "evidence_segment_ids"} for mention in result["date_mentions"])
    print("Week 12 entity/action normalization")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS: graph payload fields and segment evidence are preserved.")
    print("LIMITATION: date mentions are text only; no year or normalized date is inferred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# WEEK OUTPUT CONTRACT:
# Input: Week 6 extraction.items and stable transcript segments.
# Output: {"entities": [...], "action_items": [...], "date_mentions": [...]}.
# Entities and actions match the graph ingestion payload; date mentions remain
# evidence-linked annotations until a shared persisted date-entity schema exists.
