"""
Week 06 (14-09-2026 - 20-09-2026)
Task: Integrate Whisper/Deepgram for transcription

Why this matters:
Timestamped ASR output is the input to speaker assignment and summarization.
The provider-neutral model lets the team develop offline before credentials or
large model downloads are available.

What this script does:
It validates the ASR fixture contract used by both real adapters.
"""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.audio.asr import FixtureTranscriber


def run_smoke_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.wav"
        path.touch()
        segments = FixtureTranscriber().transcribe(path)
        assert segments and all(segment.end_ms > segment.start_ms for segment in segments)
        assert all(segment.text.strip() for segment in segments)
        return len(segments)


if __name__ == "__main__":
    print(f"ASR smoke test passed: {run_smoke_test()} segments")
