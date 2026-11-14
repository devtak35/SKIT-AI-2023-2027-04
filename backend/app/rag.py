"""Offline-first, evidence-grounded query service for the API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class _Candidate:
    score: int
    text: str
    citations: tuple[dict[str, object], ...]
    source: str


def _tokens(value: str) -> set[str]:
    stopwords = {"a", "an", "about", "and", "did", "for", "is", "it", "of", "the", "to", "we", "what", "where", "who", "will"}
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token not in stopwords}


class GroundedRAG:
    """Answer questions using only stored transcript evidence."""

    def __init__(self, transcript_repository: Any, graph_repository: Any,
                 answerer: Callable[[str, list[dict[str, object]]], str] | None = None) -> None:
        self.transcripts = transcript_repository
        self.graph = graph_repository
        self.answerer = answerer

    def answer(self, question: str, session_ids: Iterable[str] = (), top_k: int = 8) -> dict[str, object]:
        query_terms = _tokens(question)
        requested_sessions = list(dict.fromkeys(session_ids))
        sessions = requested_sessions or self.transcripts.list_session_ids()
        candidates: list[_Candidate] = []

        for session_id in sessions:
            try:
                segments = self.transcripts.list_segments(session_id, include_revisions=False)
            except Exception:
                continue
            for segment in segments:
                score = len(query_terms & _tokens(segment.text))
                if score:
                    candidates.append(_Candidate(
                        score, segment.text, (self._citation(session_id, segment),), "transcript"
                    ))

            try:
                records = self.graph.list_session_records(session_id)
            except Exception:
                records = []
            for record in records:
                score = len(query_terms & _tokens(record.text))
                if not score or not record.evidence:
                    continue
                citations = tuple(
                    self._evidence_citation(session_id, evidence) for evidence in record.evidence
                )
                candidates.append(_Candidate(score, record.text, citations, record.record_type))

        candidates.sort(key=lambda item: (-item.score, item.source, item.text))
        selected: list[_Candidate] = []
        seen_text: set[str] = set()
        for candidate in candidates:
            if candidate.text in seen_text:
                continue
            selected.append(candidate)
            seen_text.add(candidate.text)
            if len(selected) >= max(1, min(top_k, 20)):
                break

        citations: list[dict[str, object]] = []
        seen_citations: set[tuple[object, ...]] = set()
        for candidate in selected:
            for citation in candidate.citations:
                key = tuple(citation[name] for name in ("session_id", "segment_id", "revision"))
                if key not in seen_citations:
                    citations.append(citation)
                    seen_citations.add(key)

        insufficient = not selected or not citations
        if insufficient:
            answer = "Insufficient evidence for this question."
        else:
            context = [candidate.text for candidate in selected]
            answer = self.answerer(question, [{"text": text} for text in context]) if self.answerer else " ".join(context)

        return {
            "answer": answer,
            "citations": citations,
            "insufficient_evidence": insufficient,
            "retrieval_metadata": {
                "evidence_count": len(citations),
                "query_scope": "selected_sessions" if requested_sessions else "all_sessions",
                "candidate_count": len(selected),
            },
        }

    @staticmethod
    def _citation(session_id: str, segment: Any) -> dict[str, object]:
        return {
            "session_id": session_id,
            "segment_id": segment.segment_id,
            "revision": segment.revision,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "quote": segment.text,
        }

    def _evidence_citation(self, session_id: str, evidence: dict[str, object]) -> dict[str, object]:
        segment_id = str(evidence["segment_id"])
        revision = int(evidence.get("segment_revision", evidence.get("revision", 1)))
        for segment in self.transcripts.list_segments(session_id, include_revisions=True):
            if segment.segment_id == segment_id and segment.revision == revision:
                return self._citation(session_id, segment)
        return {
            "session_id": session_id,
            "segment_id": segment_id,
            "revision": revision,
            "start_ms": int(evidence.get("start_ms") or 0),
            "end_ms": int(evidence.get("end_ms") or 0),
            "quote": "",
        }
