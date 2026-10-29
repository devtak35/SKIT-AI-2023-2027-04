"""Playback-position to transcript synchronization helpers.

The browser can use this module's JSON contract without knowing anything
about ASR providers.  Intervals are half-open: a position at ``end_ms`` moves
to the next segment, which avoids duplicate highlighting at boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Iterable


@dataclass(frozen=True)
class PlaybackSegment:
    segment_id: str
    start_ms: int
    end_ms: int
    speaker_id: str
    text: str
    revision: int = 1

    def __post_init__(self) -> None:
        if not self.segment_id.strip() or not self.speaker_id.strip():
            raise ValueError("segment_id and speaker_id must not be empty")
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("segment interval must satisfy 0 <= start_ms < end_ms")
        if self.revision < 1:
            raise ValueError("revision must be at least 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_segments(segments: Iterable[PlaybackSegment]) -> list[PlaybackSegment]:
    """Validate and sort transcript intervals for deterministic UI playback."""
    ordered = sorted(segments, key=lambda item: (item.start_ms, item.end_ms, item.segment_id))
    for previous, current in zip(ordered, ordered[1:]):
        if current.start_ms < previous.start_ms:
            raise ValueError("playback segments must be ordered by start_ms")
    return ordered


def segment_at(segments: Iterable[PlaybackSegment], position_ms: int) -> PlaybackSegment | None:
    """Return the first segment containing a position, or ``None`` in a gap."""
    if position_ms < 0:
        raise ValueError("position_ms must not be negative")
    ordered = normalize_segments(segments)
    for segment in ordered:
        if segment.start_ms <= position_ms < segment.end_ms:
            return segment
    return None


def seek_position(segment: PlaybackSegment) -> int:
    """Return the media position a UI should seek to when citing a segment."""
    return segment.start_ms
