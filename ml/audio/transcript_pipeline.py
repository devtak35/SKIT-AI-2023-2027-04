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

try:  # Support package imports and direct execution from the repository root.
    from .asr import FixtureTranscriber, TranscriptSegment, Transcriber
    from .diarization import DiarizationSegment, Diarizer, FixtureDiarizer
except ImportError:  # pragma: no cover - exercised by direct script execution
    from ml.audio.asr import FixtureTranscriber, TranscriptSegment, Transcriber
    from ml.audio.diarization import DiarizationSegment, Diarizer, FixtureDiarizer


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

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def overlap_ms(left_start: int, left_end: int, right_start: int, right_end: int) -> int:
    return max(0, min(left_end, right_end) - max(left_start, right_start))


def align_segments(asr: list[TranscriptSegment], diarization: list[DiarizationSegment]) -> list[TranscriptTurn]:
    """Join ASR to the speaker with maximum overlap; unknown is explicit."""
    turns = []
    for index, segment in enumerate(asr):
        matches = [(overlap_ms(segment.start_ms, segment.end_ms, item.start_ms, item.end_ms), item) for item in diarization]
        matches = [(score, item) for score, item in matches if score > 0]
        match = max(matches, key=lambda pair: pair[0])[1] if matches else None
        turns.append(TranscriptTurn(
            turn_id=f"turn-{index:04d}", start_ms=segment.start_ms, end_ms=segment.end_ms,
            speaker=match.speaker if match else "UNKNOWN", text=segment.text,
            asr_segment_id=segment.segment_id, diarization_segment_id=match.segment_id if match else None,
            confidence=segment.confidence,
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
