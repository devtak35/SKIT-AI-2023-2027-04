"""
Week 07 (21-09-2026 - 27-09-2026)
Task: Integrate Pyannote for speaker diarization

Why this matters:
Speaker labels allow downstream extraction to attribute decisions and action
items. This fixture keeps the contract testable while Pyannote remains optional.

What this script does:
It validates timestamped speaker segments from the diarization adapter.
"""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from week7_diarization import FixtureDiarizer


def run_smoke_test() -> int:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "fixture.wav"
        path.touch()
        segments = FixtureDiarizer().diarize(path)
        assert segments and all(segment.speaker for segment in segments)
        assert all(segment.end_ms > segment.start_ms for segment in segments)
        return len(segments)


if __name__ == "__main__":
    print(f"diarization smoke test passed: {run_smoke_test()} speakers segments")
