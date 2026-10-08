"""Small deterministic, session-scoped retrieval layer.

This is intentionally provider-free. It provides the contract needed by the
API and frontend before a vector database or knowledge graph is introduced.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Mapping


@dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    session_id: str
    record_type: str
    text: str
    evidence_segment_ids: tuple[str, ...]
    confidence: float | None = None


class EvidenceRetriever:
    """Retrieve records using normalized token overlap within one session."""

    def __init__(self, records: Iterable[EvidenceRecord] = ()) -> None:
        self._records: list[EvidenceRecord] = list(records)

    def add(self, record: EvidenceRecord) -> None:
        if not record.session_id or not record.text.strip():
            raise ValueError("records require a session_id and non-empty text")
        if not record.evidence_segment_ids:
            raise ValueError("records require at least one evidence segment ID")
        self._records.append(record)

    def search(self, session_id: str, query: str, *, limit: int = 5) -> list[EvidenceRecord]:
        if not session_id or not query.strip():
            return []
        if limit < 1:
            raise ValueError("limit must be positive")
        query_terms = _tokens(query)
        scored: list[tuple[int, EvidenceRecord]] = []
        for record in self._records:
            if record.session_id != session_id:
                continue
            score = len(query_terms & _tokens(record.text))
            if score:
                scored.append((score, record))
        scored.sort(key=lambda item: (-item[0], item[1].record_id))
        return [record for _, record in scored[:limit]]

    def answer(self, session_id: str, query: str, *, limit: int = 5) -> dict[str, object]:
        records = self.search(session_id, query, limit=limit)
        if not records:
            return {
                "answer": "Insufficient evidence in this session.",
                "insufficient_evidence": True,
                "records": [],
                "source_segment_ids": [],
            }
        source_ids = sorted({segment_id for record in records for segment_id in record.evidence_segment_ids})
        return {
            "answer": " ".join(record.text for record in records),
            "insufficient_evidence": False,
            "records": [record_to_dict(record) for record in records],
            "source_segment_ids": source_ids,
        }


def record_to_dict(record: EvidenceRecord) -> dict[str, object]:
    return {
        "record_id": record.record_id,
        "session_id": record.session_id,
        "type": record.record_type,
        "text": record.text,
        "evidence_segment_ids": list(record.evidence_segment_ids),
        "confidence": record.confidence,
    }


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def records_from_extraction(session_id: str, extraction: Mapping[str, object]) -> list[EvidenceRecord]:
    """Convert validated pipeline extraction output into retrieval records."""
    raw_items = extraction.get("items", [])
    if not isinstance(raw_items, list):
        raise ValueError("extraction.items must be a list")
    records: list[EvidenceRecord] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            raise ValueError("extraction items must be objects")
        evidence = item.get("evidence_segment_ids")
        if not isinstance(evidence, list) or not all(isinstance(value, str) for value in evidence):
            raise ValueError("each extraction item needs evidence_segment_ids")
        records.append(EvidenceRecord(
            record_id=str(item["id"]),
            session_id=session_id,
            record_type=str(item["type"]),
            text=str(item["text"]),
            evidence_segment_ids=tuple(evidence),
            confidence=float(item["confidence"]),
        ))
    return records
