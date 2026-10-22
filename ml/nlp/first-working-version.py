"""
Week 10 (12-10-2026)
Task: Finalize the first working version

Why this matters:
The prompt and evidence rules now need one provider-independent entry point.
The existing injected-generator pipeline is the stable seam for later model
providers and for deterministic integration tests.

What this script does:
It verifies that the first pipeline can validate a grounded summary response.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for import_path in (ROOT, ROOT / "ml" / "nlp"):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from ml.nlp.week6_summarization_pipeline import SummarizationPipeline


def fixture_generator(messages: list[dict[str, str]]) -> dict[str, object]:
    segment_id = "turn-0000"
    return {"text": "The audio pipeline will ship on Friday.", "covered_segment_ids": [segment_id]}


def run_check() -> dict[str, object]:
    segments = [{"segment_id": "turn-0000", "revision": 1, "is_final": True, "start_ms": 0, "end_ms": 1000, "speaker_label": "SPEAKER_00", "text": "The audio pipeline will ship on Friday.", "asr_confidence": 0.98}]
    # The week 6 pipeline makes two generator calls; provide the contract shape
    # required by each call based on the system prompt content.
    def generate(messages: list[dict[str, str]]) -> dict[str, object]:
        if "action_item" in messages[0]["content"] or "extraction" in messages[0]["content"]:
            return {"items": [{"id": "action-1", "type": "action_item", "text": "Ship the audio pipeline on Friday.", "confidence": 0.91, "evidence_segment_ids": ["turn-0000"]}]}
        return fixture_generator(messages)
    output = SummarizationPipeline(generate).process(segments)
    assert output["summary"]["covered_segment_ids"] == ["turn-0000"]
    return output


if __name__ == "__main__":
    print(f"[PASS] Garvit Week 10: {run_check()}")

