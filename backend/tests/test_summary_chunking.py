import json

import pytest

from ml.nlp.summarization_pipeline import SummarizationPipeline


class RequestTooLarge(RuntimeError):
    status_code = 413


def _segments(count: int) -> list[dict[str, object]]:
    return [{
        "segment_id": f"seg-{index:03d}",
        "revision": 1,
        "is_final": True,
        "start_ms": index * 1000,
        "end_ms": (index + 1) * 1000,
        "speaker_label": "SPEAKER_00",
        "text": f"Transcript turn {index}.",
        "asr_confidence": 0.95,
    } for index in range(count)]


def test_413_retries_in_chunks_and_merges_citations_and_duplicate_records() -> None:
    requests: list[tuple[str, list[str]]] = []

    def generate(messages: list[dict[str, str]]) -> dict[str, object]:
        task = messages[0]["content"]
        label = "summary" if task.startswith("You write concise") else "extraction"
        transcript = json.loads(messages[1]["content"].split("TRANSCRIPT_SEGMENTS_JSON:\n", 1)[1])
        segment_ids = [item["segment_id"] for item in transcript]
        requests.append((label, segment_ids))
        if len(segment_ids) > 2:
            raise RequestTooLarge("payload exceeds test limit")
        if label == "summary":
            return {"text": f"Summary for {segment_ids[0]}–{segment_ids[-1]}.", "covered_segment_ids": segment_ids}
        return {"items": [{
            "id": "item-1",
            "type": "topic",
            "text": "Release readiness",
            "confidence": 0.9,
            "evidence_segment_ids": segment_ids,
        }]}

    result = SummarizationPipeline(generate).process(_segments(4))

    assert len(requests) == 6
    assert result["summary"]["covered_segment_ids"] == ["seg-000", "seg-001", "seg-002", "seg-003"]
    assert result["summary"]["text"] == "Summary for seg-000–seg-001. Summary for seg-002–seg-003."
    assert len(result["extraction"]["items"]) == 1
    item = result["extraction"]["items"][0]
    assert item["id"].startswith("chunk-")
    assert item["evidence_segment_ids"] == ["seg-000", "seg-001", "seg-002", "seg-003"]


def test_413_for_one_oversized_segment_returns_actionable_error() -> None:
    def generate(_messages: list[dict[str, str]]) -> dict[str, object]:
        raise RequestTooLarge("payload exceeds test limit")

    with pytest.raises(ValueError, match="single transcript segment is too large"):
        SummarizationPipeline(generate).process(_segments(1))
