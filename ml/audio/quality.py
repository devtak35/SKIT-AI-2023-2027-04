"""Deterministic quality and provenance metadata for audio-derived records.

This module deliberately uses PCM bytes and transcript intervals only.  It is
an explainable triage signal, not a replacement for WER/DER measurements from
real recordings or a calibrated confidence model.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable


@dataclass(frozen=True)
class AudioQualityMetadata:
    sample_rate_hz: int
    channels: int
    duration_ms: int
    rms: float
    peak: float
    silence_ratio: float
    clipping_ratio: float
    source: str

    @property
    def quality_flags(self) -> tuple[str, ...]:
        """Human-readable triage flags; these are not model probabilities."""
        flags: list[str] = []
        if self.silence_ratio >= 0.95:
            flags.append("mostly_silent")
        elif self.silence_ratio >= 0.70:
            flags.append("low_signal")
        if self.clipping_ratio > 0:
            flags.append("clipping")
        return tuple(flags)

    @property
    def quality_score(self) -> float:
        """Bounded, explainable score for routing/review, not accuracy."""
        score = 1.0 - min(1.0, self.silence_ratio)
        if self.clipping_ratio:
            score *= max(0.0, 1.0 - self.clipping_ratio)
        return round(score, 4)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["quality_flags"] = list(self.quality_flags)
        result["quality_score"] = self.quality_score
        return result


def pcm16_quality(
    pcm_s16le: bytes,
    *,
    sample_rate_hz: int,
    channels: int = 1,
    source: str = "unknown",
    silence_threshold: float = 0.01,
) -> AudioQualityMetadata:
    """Calculate bounded quality metadata from little-endian signed PCM16."""
    if not pcm_s16le or len(pcm_s16le) % 2:
        raise ValueError("PCM16 data must contain at least one complete sample")
    if sample_rate_hz <= 0 or channels <= 0:
        raise ValueError("sample_rate_hz and channels must be positive")
    if not source.strip():
        raise ValueError("source must not be empty")
    if not 0 <= silence_threshold <= 1:
        raise ValueError("silence_threshold must be between 0 and 1")

    values = [int.from_bytes(pcm_s16le[index:index + 2], "little", signed=True) for index in range(0, len(pcm_s16le), 2)]
    normalized = [abs(value) / 32768.0 for value in values]
    return AudioQualityMetadata(
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        duration_ms=round(len(values) / channels * 1000 / sample_rate_hz),
        rms=math.sqrt(sum(value * value for value in normalized) / len(normalized)),
        peak=max(normalized),
        silence_ratio=sum(value < silence_threshold for value in normalized) / len(normalized),
        clipping_ratio=sum(value >= 0.999 for value in normalized) / len(normalized),
        source=source,
    )


def overlap_pairs(segments: Iterable[dict[str, Any]]) -> list[tuple[str, str]]:
    """Return deterministic pairs of intervals with positive intersection."""
    materialized = list(segments)
    pairs: list[tuple[str, str]] = []
    for segment in materialized:
        if not str(segment.get("segment_id", "")).strip():
            raise ValueError("each segment must have a segment_id")
        if int(segment["start_ms"]) < 0 or int(segment["end_ms"]) <= int(segment["start_ms"]):
            raise ValueError("segment interval must satisfy 0 <= start_ms < end_ms")
    for index, left in enumerate(materialized):
        for right in materialized[index + 1:]:
            if min(int(left["end_ms"]), int(right["end_ms"])) > max(int(left["start_ms"]), int(right["start_ms"])):
                pairs.append((str(left["segment_id"]), str(right["segment_id"])))
    return pairs
