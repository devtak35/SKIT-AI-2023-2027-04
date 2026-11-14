

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping, Sequence
from typing import Any
from uuid import uuid4

from . import final_prompt_templates as prompts


JsonGenerator = Callable[[list[dict[str, str]]], str | Mapping[str, Any]]
ALLOWED_ITEM_TYPES = {"person", "topic", "decision", "action_item"}


class PipelineOutputError(ValueError):
    """Raised when a model response is malformed or violates the output contract."""


_INLINE_SEGMENT_LIST = re.compile(r"\(\s*([A-Za-z0-9_-]+(?:\s*,\s*[A-Za-z0-9_-]+)+)\s*\)")


def remove_inline_segment_references(text: str, segment_ids: set[str]) -> str:
    """Remove parenthesized shorthand citations that duplicate structured IDs."""
    id_tokens = set(segment_ids)
    id_tokens.update(segment_id.rsplit("-", 1)[-1] for segment_id in segment_ids)

    def remove_known_list(match: re.Match[str]) -> str:
        tokens = [token.strip() for token in match.group(1).split(",")]
        return "" if len(tokens) >= 2 and all(token in id_tokens for token in tokens) else match.group(0)

    cleaned = _INLINE_SEGMENT_LIST.sub(remove_known_list, text)
    cleaned = re.sub(r"\s+([,.;!?])", r"\1", cleaned)
    return re.sub(r" {2,}", " ", cleaned).strip()


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

        validated_summary = self._generate_with_payload_fallback(
            segments, label="summary", build_messages=prompts.build_summary_messages,
        )
        validated_extraction = self._generate_with_payload_fallback(
            segments, label="extraction", build_messages=prompts.build_extraction_messages,
        )
        # Validate merged output again against the full source set.
        validated_summary = self._validate_summary(validated_summary, valid_ids)
        validated_extraction = self._validate_extraction(validated_extraction, valid_ids)
        return {"summary": validated_summary, "extraction": validated_extraction}

    def _generate_with_payload_fallback(
        self,
        segments: Sequence[Mapping[str, Any]],
        *,
        label: str,
        build_messages: Callable[[Sequence[Mapping[str, Any]]], list[dict[str, str]]],
    ) -> dict[str, Any]:
        """Retry only oversized provider prompts by splitting their evidence."""
        valid_ids = {str(segment["segment_id"]) for segment in segments}
        validator = self._validate_summary if label == "summary" else self._validate_extraction
        try:
            response = self._decode(self.generate_json(build_messages(segments)), label)
            return validator(response, valid_ids)
        except Exception as error:
            if getattr(error, "status_code", None) != 413:
                raise
            if len(segments) < 2:
                raise ValueError(
                    "A single transcript segment is too large for Groq. Edit or split that segment, then retry."
                ) from error

        midpoint = len(segments) // 2
        left = self._generate_with_payload_fallback(
            segments[:midpoint], label=label, build_messages=build_messages,
        )
        right = self._generate_with_payload_fallback(
            segments[midpoint:], label=label, build_messages=build_messages,
        )
        if label == "summary":
            parts = [part for part in (left["text"].strip(), right["text"].strip()) if part]
            return {
                "text": " ".join(parts),
                "covered_segment_ids": list(dict.fromkeys(
                    left["covered_segment_ids"] + right["covered_segment_ids"]
                )),
            }

        merged: list[dict[str, Any]] = []
        positions: dict[tuple[str, str], int] = {}
        for item in left["items"] + right["items"]:
            key = (item["type"], " ".join(item["text"].split()).casefold())
            if key in positions:
                existing = merged[positions[key]]
                existing["evidence_segment_ids"] = list(dict.fromkeys(
                    existing["evidence_segment_ids"] + item["evidence_segment_ids"]
                ))
                existing["confidence"] = max(existing["confidence"], item["confidence"])
                continue
            positions[key] = len(merged)
            merged.append({
                **item,
                # Each chunk may emit the same local ID (for example, "item-1").
                # Keep merged records distinct for downstream graph ingestion.
                "id": f"chunk-{uuid4().hex}-{item['id']}",
            })
        return {"items": merged}

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
        return {
            "text": remove_inline_segment_references(text, valid_ids),
            "covered_segment_ids": citations,
        }

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
