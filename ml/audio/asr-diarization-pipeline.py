"""
Week 08 (28-09-2026 - 04-10-2026)
Task: Combine ASR and diarization into one pipeline

Why this matters:
This is Dhruv's first complete handoff to summarization: text, timestamps,
speaker labels, and confidence are emitted together in one predictable shape.

What this script does:
It runs the complete offline ASR-plus-diarization fixture pipeline and checks
speaker assignment by timestamp overlap.
"""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.audio.asr import FixtureTranscriber
from ml.audio.diarization import FixtureDiarizer
from ml.audio.transcript_pipeline import AudioTranscriptPipeline


def run_smoke_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.wav"
        path.touch()
        turns = AudioTranscriptPipeline(FixtureTranscriber(), FixtureDiarizer()).process(path)
        assert [turn.speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01"]
        assert all(turn.text and turn.end_ms > turn.start_ms for turn in turns)
        return len(turns)


if __name__ == "__main__":
    print(f"combined pipeline smoke test passed: {run_smoke_test()} turns")
