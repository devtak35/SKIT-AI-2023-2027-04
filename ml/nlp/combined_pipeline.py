"""Production-shaped orchestration for Garvit's NLP boundary.

The module remains provider independent.  A caller supplies the same JSON
generator used by the Week 6 pipeline, while this layer creates versioned,
revision-specific records for the graph and frontend contracts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .confidence import assess_support
from .week6_summarization_pipeline import SummarizationPipeline
from .week12_entity_extraction import normalize_extraction


NLP_OUTPUT_VERSION = "1.0"
PRODUCER = "garvit"


def _evidence_refs(ids: Sequence[str], segments: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    indexed = {str(segment["segment_id"]): segment for segment in segments}
    refs: list[dict[str, Any]] = []
    for segment_id in ids:
        segment = indexed[segment_id]
        refs.append({
            "segment_id": segment_id,
            "revision": segment["revision"],
            "start_ms": segment["start_ms"],
            "end_ms": segment["end_ms"],
        })
    return refs


class MeetingNlpPipeline:
    """Create safe display and graph payloads from final transcript evidence."""

    def __init__(self, generate_json) -> None:
        self._pipeline = SummarizationPipeline(generate_json)

    def process(
        self,
        *,
        session_id: str,
        segments: Sequence[Mapping[str, Any]],
        summary_version: int = 1,
    ) -> dict[str, Any]:
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id must be a non-empty string")
        if isinstance(summary_version, bool) or not isinstance(summary_version, int) or summary_version < 1:
            raise ValueError("summary_version must be a positive integer")

        # The Week 5 prompt validators reject provisional or malformed turns.
        raw = self._pipeline.process(segments)
        summary = raw["summary"]
        extraction = raw["extraction"]
        normalized = normalize_extraction(extraction, segments)

        summary_assessment = assess_support(
            summary["text"], summary["covered_segment_ids"], segments
        ) if summary["text"].strip() else {
            "method": "lexical-evidence-support-v1", "score": 1.0,
            "status": "accepted", "model_confidence": None,
            "components": {"lexical_coverage": 1.0, "citation_coverage": 1.0, "asr_quality": 1.0},
            "reasons": ["empty summary has no unsupported claims"],
        }

        item_assessments: dict[str, dict[str, Any]] = {}
        for item in extraction["items"]:
            item_assessments[item["id"]] = assess_support(
                item["text"], item["evidence_segment_ids"], segments,
                model_confidence=item["confidence"],
            )

        def enrich(record: Mapping[str, Any]) -> dict[str, Any]:
            value = dict(record)
            source_ids = value.pop("evidence_segment_ids")
            value["evidence"] = _evidence_refs(source_ids, segments)
            value["properties"] = {
                **dict(value.get("properties", {})),
                "support_assessment": item_assessments[value["id"]],
            }
            return value

        entities = [enrich(item) for item in normalized["entities"]]
        action_items = [enrich(item) for item in normalized["action_items"]]
        graph_entities = [item for item in entities if item["properties"]["support_assessment"]["status"] == "accepted"]
        graph_actions = [item for item in action_items if item["properties"]["support_assessment"]["status"] == "accepted"]

        display_actions = [{
            "id": item["id"],
            "text": item["description"],
            "owner": item.get("owner_entity_id"),
            "owner_status": item["owner_status"],
            "due_date_text": item.get("due_date_text"),
            "status": item["status"],
            "confidence": item["confidence"],
            "support": item["properties"]["support_assessment"],
            "evidence": item["evidence"],
        } for item in action_items]

        return {
            "schema_version": NLP_OUTPUT_VERSION,
            "session_id": session_id,
            "summary": {
                "version": summary_version,
                "text": summary["text"],
                "source_segment_ids": summary["covered_segment_ids"],
                "evidence": _evidence_refs(summary["covered_segment_ids"], segments),
                "support": summary_assessment,
            },
            "entities": entities,
            "action_items": action_items,
            "date_mentions": normalized["date_mentions"],
            "graph_batch": {
                "session_id": session_id,
                "producer": PRODUCER,
                "producer_version": NLP_OUTPUT_VERSION,
                "entities": graph_entities,
                "action_items": graph_actions,
                "relationships": [],
            },
            "display": {
                "summary": summary["text"],
                "summary_support": summary_assessment,
                "evidence_turn_count": len(summary["covered_segment_ids"]),
                "action_items": display_actions,
            },
        }
