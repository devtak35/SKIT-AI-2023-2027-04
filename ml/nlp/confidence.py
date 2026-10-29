"""Explainable support scoring for evidence-linked NLP output.

This is intentionally a deterministic safety check, not a claim that lexical
overlap can prove factuality.  It flags weakly grounded generated text before
the text is sent to durable graph storage.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any


TOKEN_PATTERN = re.compile(r"[a-z0-9][a-z0-9'-]*", re.IGNORECASE)
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in",
    "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "will",
    "with", "we", "i", "you", "they", "he", "she", "our", "their",
}


@dataclass(frozen=True)
class ConfidencePolicy:
    """Documented thresholds for deterministic evidence-support triage."""

    accept_threshold: float = 0.72
    review_threshold: float = 0.45

    def validate(self) -> None:
        if not 0 < self.review_threshold < self.accept_threshold <= 1:
            raise ValueError("thresholds must satisfy 0 < review < accept <= 1")


DEFAULT_POLICY = ConfidencePolicy()


def _content_tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in TOKEN_PATTERN.findall(text)
        if len(token) > 1 and token.casefold() not in STOP_WORDS
    }


def assess_support(
    text: str,
    evidence_segment_ids: Sequence[str],
    segments: Sequence[Mapping[str, Any]],
    *,
    model_confidence: float | None = None,
    policy: ConfidencePolicy = DEFAULT_POLICY,
) -> dict[str, Any]:
    """Return an evidence-support assessment for a generated claim.

    Score components are deliberately exposed so a reviewer can see whether a
    record was flagged because citations were absent, words were unsupported,
    or source ASR quality was poor.  The score is a triage signal, not a
    calibrated probability.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    if not evidence_segment_ids or not all(isinstance(value, str) and value for value in evidence_segment_ids):
        raise ValueError("at least one non-empty evidence segment ID is required")
    policy.validate()
    if model_confidence is not None and (
        isinstance(model_confidence, bool)
        or not isinstance(model_confidence, (int, float))
        or not math.isfinite(model_confidence)
        or not 0 <= model_confidence <= 1
    ):
        raise ValueError("model_confidence must be a finite number in [0, 1]")

    indexed = {
        segment.get("segment_id"): segment
        for segment in segments
        if isinstance(segment.get("segment_id"), str)
    }
    missing = sorted(set(evidence_segment_ids) - set(indexed))
    cited = [indexed[segment_id] for segment_id in evidence_segment_ids if segment_id in indexed]
    if missing:
        raise ValueError(f"evidence references unknown segment IDs: {missing}")

    claim_tokens = _content_tokens(text)
    evidence_tokens = set().union(*(_content_tokens(str(item.get("text", ""))) for item in cited))
    lexical_coverage = len(claim_tokens & evidence_tokens) / len(claim_tokens) if claim_tokens else 0.0
    asr_values = [
        float(item["asr_confidence"])
        for item in cited
        if isinstance(item.get("asr_confidence"), (int, float))
        and not isinstance(item.get("asr_confidence"), bool)
    ]
    asr_quality = sum(asr_values) / len(asr_values) if asr_values else 1.0
    citation_coverage = 1.0
    score = round(0.75 * lexical_coverage + 0.15 * citation_coverage + 0.10 * asr_quality, 4)

    if score >= policy.accept_threshold:
        status = "accepted"
    elif score >= policy.review_threshold:
        status = "review_required"
    else:
        status = "rejected"
    reasons: list[str] = []
    if lexical_coverage < 0.6:
        reasons.append("generated wording has limited lexical support in its cited evidence")
    if asr_quality < 0.75:
        reasons.append("cited source has low average ASR confidence")
    if status == "accepted" and not reasons:
        reasons.append("cited evidence has sufficient deterministic support")

    return {
        "method": "lexical-evidence-support-v1",
        "score": score,
        "status": status,
        "model_confidence": model_confidence,
        "components": {
            "lexical_coverage": round(lexical_coverage, 4),
            "citation_coverage": citation_coverage,
            "asr_quality": round(asr_quality, 4),
        },
        "reasons": reasons,
    }
