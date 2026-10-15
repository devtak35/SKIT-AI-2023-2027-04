"""
Week 09 (05-10-2026 - 11-10-2026)
Task: Test on sample recordings, measure accuracy

Why this matters:
Week 08 combined ASR and diarization into the speaker-labelled transcript
contract used by summarization and storage. Measuring that contract on small,
repeatable fixtures gives the team a baseline before real recordings and model
downloads are available, while also exposing whether missing diarization loses
transcript text.

What this script does:
It runs representative meeting fixtures through the combined pipeline and
reports word error rate, speaker-label accuracy, timestamp coverage, and
UNKNOWN-speaker fallback behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from week6_asr import TranscriptSegment
from week7_diarization import DiarizationSegment
from week8_transcript_pipeline import AudioTranscriptPipeline, TranscriptTurn


@dataclass(frozen=True)
class SampleRecording:
    name: str
    asr: list[TranscriptSegment]
    diarization: list[DiarizationSegment]
    expected_text: str
    expected_speakers: list[str]


class FixtureTranscriber:
    def __init__(self, segments: list[TranscriptSegment]) -> None:
        self.segments = segments

    def transcribe(self, audio_path: Path) -> list[TranscriptSegment]:
        if not Path(audio_path).is_file():
            raise FileNotFoundError(audio_path)
        return list(self.segments)


class FixtureDiarizer:
    def __init__(self, segments: list[DiarizationSegment]) -> None:
        self.segments = segments

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        if not Path(audio_path).is_file():
            raise FileNotFoundError(audio_path)
        return list(self.segments)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Return token-level WER using the standard Levenshtein distance."""
    expected, actual = _tokens(reference), _tokens(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0

    previous = list(range(len(actual) + 1))
    for row, expected_token in enumerate(expected, start=1):
        current = [row]
        for column, actual_token in enumerate(actual, start=1):
            substitution = previous[column - 1] + (expected_token != actual_token)
            insertion = current[column - 1] + 1
            deletion = previous[column] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1] / len(expected)


def speaker_accuracy(turns: list[TranscriptTurn], expected: list[str]) -> float:
    if len(turns) != len(expected):
        return 0.0
    return sum(turn.speaker == label for turn, label in zip(turns, expected)) / len(expected)


def timestamp_coverage(turns: list[TranscriptTurn], expected_duration_ms: int) -> float:
    covered_ms = sum(turn.end_ms - turn.start_ms for turn in turns)
    return covered_ms / expected_duration_ms if expected_duration_ms else 0.0


def sample_recordings() -> list[SampleRecording]:
    return [
        SampleRecording(
            name="clear_two-speaker-meeting",
            asr=[
                TranscriptSegment("asr-0001", 0, 2400, "We will ship the audio pipeline on Friday."),
                TranscriptSegment("asr-0002", 2400, 4800, "Priya owns the release checklist."),
            ],
            diarization=[
                DiarizationSegment("spk-0001", 0, 2400, "SPEAKER_00"),
                DiarizationSegment("spk-0002", 2400, 4800, "SPEAKER_01"),
            ],
            expected_text="We will ship the audio pipeline on Friday. Priya owns the release checklist.",
            expected_speakers=["SPEAKER_00", "SPEAKER_01"],
        ),
        SampleRecording(
            name="minor-asr-deletion",
            asr=[
                TranscriptSegment("asr-0001", 0, 2200, "Let's review the sprint plan."),
                TranscriptSegment("asr-0002", 2200, 4200, "The demo is scheduled for Monday."),
            ],
            diarization=[
                DiarizationSegment("spk-0001", 0, 2200, "SPEAKER_00"),
                DiarizationSegment("spk-0002", 2200, 4200, "SPEAKER_01"),
            ],
            expected_text="Let's review the sprint plan today. The demo is scheduled for Monday.",
            expected_speakers=["SPEAKER_00", "SPEAKER_01"],
        ),
        SampleRecording(
            name="missing-diarization-fallback",
            asr=[
                TranscriptSegment("asr-0001", 0, 1800, "The recording remains searchable."),
                TranscriptSegment("asr-0002", 1800, 3600, "We need a backup speaker label."),
            ],
            diarization=[DiarizationSegment("spk-0001", 0, 1800, "SPEAKER_00")],
            expected_text="The recording remains searchable. We need a backup speaker label.",
            expected_speakers=["SPEAKER_00", "UNKNOWN"],
        ),
    ]


def evaluate(recording: SampleRecording, audio_path: Path) -> dict[str, float | str | int]:
    pipeline = AudioTranscriptPipeline(
        FixtureTranscriber(recording.asr), FixtureDiarizer(recording.diarization)
    )
    turns = pipeline.process(audio_path)
    hypothesis = " ".join(turn.text for turn in turns)
    expected_duration_ms = max(segment.end_ms for segment in recording.asr)
    return {
        "name": recording.name,
        "turns": len(turns),
        "wer": word_error_rate(recording.expected_text, hypothesis),
        "speaker_accuracy": speaker_accuracy(turns, recording.expected_speakers),
        "timestamp_coverage": timestamp_coverage(turns, expected_duration_ms),
        "unknown_turns": sum(turn.speaker == "UNKNOWN" for turn in turns),
    }


def run_evaluation() -> list[dict[str, float | str | int]]:
    with tempfile.TemporaryDirectory() as directory:
        audio_path = Path(directory) / "sample-meeting.wav"
        audio_path.touch()
        results = [evaluate(recording, audio_path) for recording in sample_recordings()]

    assert all(result["turns"] > 0 for result in results)
    assert all(result["timestamp_coverage"] == 1.0 for result in results)
    assert all(result["speaker_accuracy"] == 1.0 for result in results)
    assert results[0]["wer"] == 0.0
    assert 0.0 < results[1]["wer"] < 0.2
    assert results[2]["unknown_turns"] == 1
    return results


if __name__ == "__main__":
    for result in run_evaluation():
        print(
            f"{result['name']}: turns={result['turns']} "
            f"wer={result['wer']:.3f} "
            f"speaker_accuracy={result['speaker_accuracy']:.3f} "
            f"timestamp_coverage={result['timestamp_coverage']:.3f} "
            f"unknown_turns={result['unknown_turns']}"
        )
