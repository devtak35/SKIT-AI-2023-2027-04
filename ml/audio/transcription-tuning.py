"""
Week 10 (12-10-2026)
Task: Tune settings for better transcription quality

Why this matters:
The first pipeline needs conservative quality gates before real model tuning.
Rejecting malformed or low-confidence turns prevents poor evidence from being
silently promoted into summaries and graph records.

What this script does:
It applies a deterministic confidence filter while preserving segment order.
"""


def filter_usable_turns(turns: list[dict[str, object]], minimum_confidence: float = 0.80) -> list[dict[str, object]]:
    return [turn for turn in turns if float(turn.get("confidence") or 0) >= minimum_confidence and str(turn.get("text", "")).strip()]


if __name__ == "__main__":
    sample = [{"text": "ship Friday", "confidence": 0.96}, {"text": "unclear", "confidence": 0.42}]
    result = filter_usable_turns(sample)
    assert len(result) == 1
    print(f"[PASS] Dhruv Week 10: retained {len(result)} high-confidence turn")

