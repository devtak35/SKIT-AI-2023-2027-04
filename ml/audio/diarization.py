"""
Week 07 (21-09-2026 - 27-09-2026)
Task: Integrate Pyannote for speaker diarization

Why this matters:
ASR text without speaker identity is difficult to summarize into owners and
decisions. This module adds a timestamped, provider-neutral speaker contract
that can be joined to week 6 ASR segments.

What this script does:
It provides a Pyannote adapter with lazy imports and an offline fixture diarizer
for repeatable development and integration tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class DiarizationSegment:
    segment_id: str
    start_ms: int
    end_ms: int
    speaker: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("diarization timestamps must satisfy 0 <= start_ms < end_ms")
        if not self.speaker.strip():
            raise ValueError("speaker label must not be empty")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Diarizer(Protocol):
    def diarize(self, audio_path: Path) -> list[DiarizationSegment]: ...


class FixtureDiarizer:
    def __init__(self, segments: list[DiarizationSegment] | None = None) -> None:
        self.segments = segments or [
            DiarizationSegment("spk-0001", 0, 2_500, "SPEAKER_00", 0.91),
            DiarizationSegment("spk-0002", 2_500, 5_000, "SPEAKER_01", 0.89),
        ]

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        if not Path(audio_path).is_file():
            raise FileNotFoundError(audio_path)
        return list(self.segments)


class PyannoteDiarizer:
    """Lazy-loaded pyannote adapter. The Hugging Face token stays outside source control."""

    def __init__(self, model: str = "pyannote/speaker-diarization-3.1", auth_token: str | None = None) -> None:
        self.model_name, self.auth_token = model, auth_token
        self._pipeline: Any = None

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        try:
            from pyannote.audio import Pipeline
        except ImportError as exc:
            raise RuntimeError("Install pyannote.audio to use PyannoteDiarizer") from exc
        if self._pipeline is None:
            kwargs = {"use_auth_token": self.auth_token} if self.auth_token else {}
            self._pipeline = Pipeline.from_pretrained(self.model_name, **kwargs)
        diarization = self._pipeline(str(audio_path))
        output = []
        for index, (turn, _, speaker) in enumerate(diarization.itertracks(yield_label=True)):
            output.append(DiarizationSegment(
                f"spk-{index:04d}", round(turn.start * 1000), max(round(turn.start * 1000) + 1, round(turn.end * 1000)), str(speaker)
            ))
        return output


if __name__ == "__main__":
    fixture = Path("diarization-fixture.wav")
    fixture.touch()
    print([segment.to_dict() for segment in FixtureDiarizer().diarize(fixture)])
