"""
Week 06 (14-09-2026 - 20-09-2026)
Task: Integrate Whisper/Deepgram for transcription

Why this matters:
The capture module from week 5 produces stable PCM/WAV artifacts, but the
downstream summarizer needs timestamped text. This module defines that contract
and keeps the provider choice replaceable so diarization can be added next.

What this script does:
It provides a common transcript-segment model, a local Whisper adapter, a
Deepgram HTTP adapter, and a deterministic fixture transcriber for development.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Protocol
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TranscriptSegment:
    """Provider-neutral ASR output consumed by the diarization stage."""

    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.start_ms < 0 or self.end_ms <= self.start_ms:
            raise ValueError("segment timestamps must satisfy 0 <= start_ms < end_ms")
        if not self.text.strip():
            raise ValueError("transcript text must not be empty")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Transcriber(Protocol):
    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]: ...


class FixtureTranscriber:
    """Small offline adapter used until real provider credentials are available."""

    def __init__(self, segments: list[TranscriptSegment] | None = None) -> None:
        self.segments = segments or [
            TranscriptSegment("asr-0001", 0, 2_400, "We will ship the audio pipeline on Friday.", 0.98),
            TranscriptSegment("asr-0002", 2_400, 4_800, "Priya owns the release checklist.", 0.96),
        ]

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        if not Path(audio_path).is_file():
            raise FileNotFoundError(audio_path)
        return list(self.segments)


class WhisperTranscriber:
    """Lazy-loaded local Whisper adapter; importing this module needs no ML packages."""

    def __init__(self, model_name: str = "base", language: str | None = None) -> None:
        self.model_name = model_name
        self.language = language
        self._model: Any = None

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        try:
            import whisper
        except ImportError as exc:
            raise RuntimeError("Install openai-whisper to use WhisperTranscriber") from exc
        if self._model is None:
            self._model = whisper.load_model(self.model_name)
        options: dict[str, Any] = {"task": "transcribe", "verbose": False}
        if self.language:
            options["language"] = self.language
        result = self._model.transcribe(str(audio_path), **options)
        output: list[TranscriptSegment] = []
        for index, item in enumerate(result.get("segments", [])):
            start_ms = round(float(item["start"]) * 1000)
            end_ms = max(start_ms + 1, round(float(item["end"]) * 1000))
            output.append(TranscriptSegment(f"asr-{index:04d}", start_ms, end_ms, item["text"].strip()))
        return output


class DeepgramTranscriber:
    """Minimal Deepgram REST adapter using only Python's standard library."""

    def __init__(self, api_key: str, model: str = "nova-2", endpoint: str = "https://api.deepgram.com/v1/listen") -> None:
        if not api_key.strip():
            raise ValueError("api_key must not be empty")
        self.api_key, self.model, self.endpoint = api_key, model, endpoint

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        audio = Path(audio_path).read_bytes()
        request = Request(
            f"{self.endpoint}?model={self.model}&utterances=true&punctuate=true",
            data=audio,
            headers={"Authorization": f"Token {self.api_key}", "Content-Type": "audio/wav"},
            method="POST",
        )
        with urlopen(request, timeout=60) as response:  # noqa: S310 - endpoint is configurable by caller
            payload = json.loads(response.read().decode("utf-8"))
        alternatives = payload.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])
        paragraphs = alternatives[0].get("paragraphs", {}).get("paragraphs", [])
        if not paragraphs:
            paragraphs = payload.get("results", {}).get("utterances", [])
        output = []
        for index, item in enumerate(paragraphs):
            start_ms = round(float(item.get("start", 0)) * 1000)
            end_ms = max(start_ms + 1, round(float(item.get("end", 0)) * 1000))
            text = item.get("transcript", item.get("text", "")).strip()
            if text:
                output.append(TranscriptSegment(f"asr-{index:04d}", start_ms, end_ms, text, item.get("confidence")))
        return output


if __name__ == "__main__":
    fixture = Path("asr-fixture.wav")
    fixture.touch()
    print(json.dumps([segment.to_dict() for segment in FixtureTranscriber().transcribe(fixture)], indent=2))
