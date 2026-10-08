

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from . import final_prompt_templates as prompts


JsonGenerator = Callable[[list[dict[str, str]]], str | Mapping[str, Any]]
ALLOWED_ITEM_TYPES = {"person", "topic", "decision", "action_item"}


class PipelineOutputError(ValueError):
    """Raised when a model response is malformed or violates the output contract."""


class SummarizationPipeline:
    """Run summary and extraction prompts through an injected JSON generator.

    The generator receives the standard two-message prompt and returns either
    a JSON string or an already-decoded mapping. This keeps provider setup out
    of the NLP contract and allows deterministic fixture-backed use.
    """

    def __init__(self, generate_json: JsonGenerator) -> None:
        self.generate_json = generate_json

    def process(self, segments: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """Return validated summary and extraction objects for final segments."""
        valid_ids = {segment.get("segment_id") for segment in segments}
        if not valid_ids or not all(isinstance(value, str) and value for value in valid_ids):
            raise ValueError("transcript segments must have non-empty segment_id values")
        if len(valid_ids) != len(segments):
            raise ValueError("transcript segment_id values must be unique")

        summary_messages = prompts.build_summary_messages(segments)
        extraction_messages = prompts.build_extraction_messages(segments)
        summary = self._decode(self.generate_json(summary_messages), "summary")
        extraction = self._decode(self.generate_json(extraction_messages), "extraction")

        validated_summary = self._validate_summary(summary, valid_ids)
        validated_extraction = self._validate_extraction(extraction, valid_ids)
        return {"summary": validated_summary, "extraction": validated_extraction}

    @staticmethod
    def _decode(response: str | Mapping[str, Any], label: str) -> dict[str, Any]:
        if isinstance(response, str):
            try:
                decoded = json.loads(response)
            except json.JSONDecodeError as error:
                raise PipelineOutputError(f"{label} response is not valid JSON: {error.msg}") from error
        else:
            decoded = response
        if not isinstance(decoded, Mapping):
            raise PipelineOutputError(f"{label} response must be a JSON object")
        return dict(decoded)

    @staticmethod
    def _require_exact_fields(
        value: Mapping[str, Any], expected: set[str], label: str
    ) -> None:
        actual = set(value)
        missing = expected - actual
        unexpected = actual - expected
        if missing or unexpected:
            details = []
            if missing:
                details.append(f"missing fields: {sorted(missing)}")
            if unexpected:
                details.append(f"unexpected fields: {sorted(unexpected)}")
            raise PipelineOutputError(f"{label} has " + "; ".join(details))

    @classmethod
    def _validate_summary(
        cls, summary: dict[str, Any], valid_ids: set[str]
    ) -> dict[str, Any]:
        cls._require_exact_fields(summary, {"text", "covered_segment_ids"}, "summary")
        text = summary["text"]
        citations = summary["covered_segment_ids"]
        if not isinstance(text, str):
            raise PipelineOutputError("summary.text must be a string")
        if not isinstance(citations, list) or not all(
            isinstance(value, str) for value in citations
        ):
            raise PipelineOutputError("summary.covered_segment_ids must be a list of strings")
        if len(citations) != len(set(citations)):
            raise PipelineOutputError("summary.covered_segment_ids must not contain duplicates")
        unknown = set(citations) - valid_ids
        if unknown:
            raise PipelineOutputError(f"summary cites unknown segment IDs: {sorted(unknown)}")
        if text.strip() and not citations:
            raise PipelineOutputError("a non-empty summary must cite supporting segments")
        if not text.strip() and citations:
            raise PipelineOutputError("an empty summary must not cite segments")
        return {"text": text, "covered_segment_ids": citations}

    @classmethod
    def _validate_extraction(
        cls, extraction: dict[str, Any], valid_ids: set[str]
    ) -> dict[str, Any]:
        cls._require_exact_fields(extraction, {"items"}, "extraction")
        items = extraction["items"]
        if not isinstance(items, list):
            raise PipelineOutputError("extraction.items must be a list")

        seen_ids: set[str] = set()
        normalized: list[dict[str, Any]] = []
        required_item_fields = {
            "id", "type", "text", "confidence", "evidence_segment_ids"
        }
        for index, item in enumerate(items):
            label = f"extraction.items[{index}]"
            if not isinstance(item, Mapping):
                raise PipelineOutputError(f"{label} must be an object")
            cls._require_exact_fields(item, required_item_fields, label)

            item_id = item["id"]
            if not isinstance(item_id, str) or not item_id.strip():
                raise PipelineOutputError(f"{label}.id must be a non-empty string")
            if item_id in seen_ids:
                raise PipelineOutputError(f"duplicate extraction item id: {item_id}")
            seen_ids.add(item_id)

            item_type = item["type"]
            if not isinstance(item_type, str) or item_type not in ALLOWED_ITEM_TYPES:
                raise PipelineOutputError(
                    f"{label}.type must be one of {sorted(ALLOWED_ITEM_TYPES)}"
                )
            if not isinstance(item["text"], str) or not item["text"].strip():
                raise PipelineOutputError(f"{label}.text must be a non-empty string")

            confidence = item["confidence"]
            if (
                isinstance(confidence, bool)
                or not isinstance(confidence, (int, float))
                or not math.isfinite(confidence)
                or not 0.0 <= confidence <= 1.0
            ):
                raise PipelineOutputError(f"{label}.confidence must be between 0.0 and 1.0")

            evidence_ids = item["evidence_segment_ids"]
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise PipelineOutputError(f"{label}.evidence_segment_ids must be a non-empty list")
            if not all(isinstance(value, str) for value in evidence_ids):
                raise PipelineOutputError(f"{label}.evidence_segment_ids must contain strings")
            if len(evidence_ids) != len(set(evidence_ids)):
                raise PipelineOutputError(f"{label}.evidence_segment_ids must not contain duplicates")
            unknown = set(evidence_ids) - valid_ids
            if unknown:
                raise PipelineOutputError(
                    f"{label} cites unknown segment IDs: {sorted(unknown)}"
                )
            normalized.append(
                {
                    "id": item_id,
                    "type": item_type,
                    "text": item["text"],
                    "confidence": confidence,
                    "evidence_segment_ids": evidence_ids,
                }
            )
        return {"items": normalized}


# WEEK OUTPUT CONTRACT:
# Input: Final transcript segment mappings matching the Week 5 prompt contract,
#        plus an injected callable that turns messages into JSON responses.
# Output: {"summary": {"text", "covered_segment_ids"},
#          "extraction": {"items": [{"id", "type", "text", "confidence",
#                                      "evidence_segment_ids"}]}}.
# Provider selection, credentials, storage, and persistence are outside this
# provider-independent module.
