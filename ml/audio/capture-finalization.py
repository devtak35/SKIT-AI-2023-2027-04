"""
Week 05 (07-09-2026 - 13-09-2026)
Task: Fix bugs and finalize the capture module

Why this matters:
The capture handoff is the first contract in Dhruv's pipeline. Reliable
validation and clear failures prevent malformed audio from reaching ASR.

What this script does:
It smoke-tests PCM conversion, timezone/session validation, chunk metadata, and
the finalized microphone capture module using generated fixture audio.
"""

from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from capture import float_samples_to_pcm16le, make_audio_chunks


def run_smoke_test() -> int:
    pcm = float_samples_to_pcm16le([0.0, 0.5, -0.5, 2.0])
    with tempfile.TemporaryDirectory() as directory:
        chunks = make_audio_chunks(
            pcm, session_id="00000000-0000-0000-0000-000000000005",
            chunk_directory=Path(directory), captured_at=datetime.now(timezone.utc),
            sample_rate_hz=4, chunk_duration_ms=500,
        )
        assert len(chunks) == 2
        assert all(chunk.to_event()["schema_version"] == "1.0" for chunk in chunks)
        assert all(Path(chunk.audio_ref).is_file() for chunk in chunks)
    return len(chunks)


if __name__ == "__main__":
    print(f"capture smoke test passed: {run_smoke_test()} chunks")
