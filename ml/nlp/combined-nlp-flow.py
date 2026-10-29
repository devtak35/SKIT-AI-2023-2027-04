"""
Week 13 (27-10-2026 - 02-11-2026)
Task: Combine summarization and extraction into one flow

Why this matters:
The separate summary and extraction responses must become one versioned output
without losing transcript revisions or evidence. This is the producer payload
consumed by Harsh's graph adapter and Dev's future summary storage endpoint.

What this script does:
Runs the combined provider-neutral NLP pipeline against a representative
fixture and prints its graph-safe batch.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.nlp.combined_pipeline import MeetingNlpPipeline


def main() -> int:
    case = json.loads((ROOT / "ml/nlp/fixtures/week_03_sample_transcripts.json").read_text(encoding="utf-8"))["cases"][1]
    responses = iter((case["reference_summary"], case["reference_extraction"]))
    result = MeetingNlpPipeline(lambda _messages: next(responses)).process(
        session_id="week-13-fixture", segments=case["transcript_segments"]
    )
    assert result["graph_batch"]["action_items"]
    print(json.dumps(result, indent=2))
    print("PASS: combined NLP output contains evidence-linked display and graph payloads.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
