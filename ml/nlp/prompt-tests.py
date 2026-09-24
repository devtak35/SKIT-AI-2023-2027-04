from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
NLP_DIR = REPO_ROOT / "ml" / "nlp"
sys.path.insert(0, str(NLP_DIR))

from prompt_evaluation import evaluate_fixture  # noqa: E402


def main() -> int:
    failures = evaluate_fixture()
    if failures:
        print(f"FAIL: {len(failures)} prompt/fixture check(s)")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("PASS: Week 2 prompts render all source segments and request evidence fields.")
    print("PASS: Hand-written reference outputs satisfy the documented output shapes and cite known segment IDs.")
    print("REVIEWED SCENARIOS: conditional release plan; explicit scope decision and named action owner.")
    print("LIMITATION: reference outputs are fixtures, not LLM generations; fluency, factuality, and prompt effectiveness remain unmeasured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# WEEK OUTPUT CONTRACT:
# Input: The Week 2 prompt builders and ml/nlp/fixtures/week_03_sample_transcripts.json.
# Output: A pass/fail report for prompt rendering and reference-output schema/provenance checks.
