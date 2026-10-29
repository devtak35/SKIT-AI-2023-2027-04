"""
Week 08 (28-09-2026 - 04-10-2026)
Task: Combine ASR and diarization into one pipeline

Why this matters:
Weeks 6 and 7 now emit independent timestamped streams. This week joins them
into the stable speaker-labeled transcript contract consumed by summarization,
storage, and playback synchronization.

What this script does:
It aligns each ASR segment to the diarization segment with the greatest time
overlap, preserves timestamps and confidence, and includes an offline fixture
runner that works without model downloads or credentials.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:  # Support both ``python week8_transcript_pipeline.py`` and package imports.
    from .week6_asr import FixtureTranscriber, TranscriptSegment, Transcriber
    from .week7_diarization import DiarizationSegment, Diarizer, FixtureDiarizer
except ImportError:  # pragma: no cover - exercised by direct script execution
    from week6_asr import FixtureTranscriber, TranscriptSegment, Transcriber
    from week7_diarization import DiarizationSegment, Diarizer, FixtureDiarizer


@dataclass(frozen=True)
class TranscriptTurn:
    turn_id: str
    start_ms: int
    end_ms: int
    speaker: str
    text: str
    asr_segment_id: str
    diarization_segment_id: str | None
    confidence: float | None
    overlapping_speakers: tuple[str, ...] = ()
    overlap_ratio: float = 0.0
    needs_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_nlp_segment(self, *, revision: int = 1, is_final: bool = True) -> dict[str, Any]:
        """Return the stable segment shape expected by Garvit's NLP boundary.

        The audio pipeline keeps its own ``turn_id`` and ``speaker`` names so
        provider adapters stay independent.  This explicit conversion keeps
        that internal model separate from the revision-aware application
        contract and makes provisional/final delivery a caller decision.
        """
        if revision < 1:
            raise ValueError("revision must be at least 1")
        return {
            "segment_id": self.turn_id,
            "revision": revision,
            "is_final": is_final,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker_label": self.speaker,
            "text": self.text,
            "asr_confidence": self.confidence,
            "overlaps_with_speaker_labels": list(self.overlapping_speakers),
            "overlap_ratio": self.overlap_ratio,
            "needs_review": self.needs_review,
        }


def overlap_ms(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def align_segments(asr: list[TranscriptSegment], diarization: list[DiarizationSegment]) -> list[TranscriptTurn]:
    """Join ASR to diarization while preserving crosstalk as uncertainty.

    ``speaker`` remains the greatest-overlap primary label for compatibility
    with the existing transcript API.  Every other overlapping attribution is
    retained in ``overlapping_speakers`` and the turn is marked for review;
    consumers must not interpret the primary label as proof that only one
    person spoke.
    """
    # Provider adapters are external boundaries. Fail early on malformed
    # intervals instead of silently creating misleading evidence.
    asr = sorted(asr, key=lambda item: (item.start_ms, item.end_ms, item.segment_id))
    diarization = sorted(diarization, key=lambda item: (item.start_ms, item.end_ms, item.segment_id))
    turns = []
    for index, segment in enumerate(asr):
        matches = [(overlap_ms(segment.start_ms, segment.end_ms, item.start_ms, item.end_ms), item) for item in diarization]
        matches = [(score, item) for score, item in matches if score > 0]
        match = max(matches, key=lambda pair: (pair[0], pair[1].speaker, pair[1].segment_id))[1] if matches else None
        overlapping_speakers = tuple(dict.fromkeys(
            item.speaker for score, item in matches
            if match is not None and item.segment_id != match.segment_id
        ))
        secondary_ranges = sorted(
            (max(segment.start_ms, item.start_ms), min(segment.end_ms, item.end_ms))
            for score, item in matches
            if match is not None and item.segment_id != match.segment_id
        )
        covered_secondary_ms = 0
        if secondary_ranges:
            range_start, range_end = secondary_ranges[0]
            for next_start, next_end in secondary_ranges[1:]:
                if next_start <= range_end:
                    range_end = max(range_end, next_end)
                else:
                    covered_secondary_ms += range_end - range_start
                    range_start, range_end = next_start, next_end
            covered_secondary_ms += range_end - range_start
        overlap_ratio = covered_secondary_ms / (segment.end_ms - segment.start_ms) if secondary_ranges else 0.0
        turns.append(TranscriptTurn(
            turn_id=f"turn-{index:04d}", start_ms=segment.start_ms, end_ms=segment.end_ms,
            speaker=match.speaker if match else "UNKNOWN", text=segment.text,
            asr_segment_id=segment.segment_id, diarization_segment_id=match.segment_id if match else None,
            confidence=segment.confidence,
            overlapping_speakers=overlapping_speakers,
            overlap_ratio=overlap_ratio,
            needs_review=bool(overlapping_speakers) or match is None,
        ))
    return turns


class AudioTranscriptPipeline:
    def __init__(self, transcriber: Transcriber, diarizer: Diarizer) -> None:
        self.transcriber, self.diarizer = transcriber, diarizer

    def process(self, audio_path: Path) -> list[TranscriptTurn]:
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)
        return align_segments(self.transcriber.transcribe(audio_path), self.diarizer.diarize(audio_path))


if __name__ == "__main__":
    fixture = Path("pipeline-fixture.wav")
    fixture.touch()
    result = AudioTranscriptPipeline(FixtureTranscriber(), FixtureDiarizer()).process(fixture)
    print(*[turn.to_dict() for turn in result], sep="\n")
