"""
Week 04 (31-08-2026 - 06-09-2026)
Task: Test capture reliability across both methods

Why this matters:
The ASR and downstream summary stages depend on capture events being complete,
ordered, and readable regardless of whether audio came from the microphone or
a meeting platform. These checks turn the Week 2 and Week 3 contracts into a
repeatable smoke test before real device and SDK testing begins.

What this script does:
Runs deterministic reliability checks against synthetic microphone and
platform PCM streams, covering ordering, timestamps, chunk files, source
metadata, and malformed-input handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.audio.capture import make_audio_chunks


def load_platform_module():
    module_path = Path(__file__).with_name("week_03_platform-capture.py")
    spec = importlib.util.spec_from_file_location("week_03_platform_capture", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def silent_pcm(seconds: int = 3) -> bytes:
    return struct.pack("<" + ("h" * (16_000 * seconds)), *([0] * (16_000 * seconds)))


def assert_capture_contract(events: list[dict[str, object]], expected_source: str) -> None:
    if len(events) != 3:
        raise AssertionError(f"expected three one-second chunks, got {len(events)}")
    sequences = [event["payload"]["sequence"] for event in events]
    if sequences != [0, 1, 2]:
        raise AssertionError(f"chunk order is not contiguous: {sequences}")
    timestamps = [event["payload"]["captured_at"] for event in events]
    if timestamps != sorted(timestamps):
        raise AssertionError("chunk timestamps are not monotonic")
    for event in events:
        payload = event["payload"]
        if payload["source"] != expected_source:
            raise AssertionError(f"unexpected source: {payload['source']}")
        audio_path = Path(payload["audio_ref"])
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise AssertionError(f"missing or empty audio file: {audio_path}")
        if payload["sample_rate_hz"] != 16_000 or payload["channels"] != 1:
            raise AssertionError("audio normalization contract changed")


def test_microphone_fixture() -> None:
    session_id = "12345678-1234-5678-1234-567812345678"
    with TemporaryDirectory(prefix="microphone-reliability-") as directory:
        chunks = make_audio_chunks(
            silent_pcm(),
            session_id=session_id,
            chunk_directory=Path(directory),
            captured_at=datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc),
            source="microphone",
        )
        assert_capture_contract([chunk.to_event() for chunk in chunks], "microphone")


def test_platform_fixture() -> None:
    platform = load_platform_module()
    session_id = "12345678-1234-5678-1234-567812345678"
    with TemporaryDirectory(prefix="platform-reliability-") as directory:
        adapter = platform.PlatformCaptureAdapter(
            session_id=session_id,
            chunk_directory=Path(directory),
            source="google_meet",
        )
        event = next(
            platform.mock_platform_events(
                provider="google_meet",
                meeting_id="reliability-meeting",
                pcm_s16le=silent_pcm(),
                started_at=datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc),
            )
        )
        chunks = adapter.ingest(event)
        assert_capture_contract([chunk.to_event() for chunk in chunks], "google_meet")


def test_invalid_pcm_is_rejected() -> None:
    try:
        make_audio_chunks(
            b"odd",
            session_id="12345678-1234-5678-1234-567812345678",
            chunk_directory=Path("unused"),
            captured_at=datetime(2026, 8, 31, 9, 0, tzinfo=timezone.utc),
        )
    except ValueError as error:
        if "complete audio frames" not in str(error):
            raise AssertionError(f"unexpected validation error: {error}") from error
    else:
        raise AssertionError("incomplete PCM frame was accepted")


def main() -> int:
    tests = (test_microphone_fixture, test_platform_fixture, test_invalid_pcm_is_rejected)
    for test in tests:
        test()
        print(f"[PASS] {test.__name__}")
    print("Result: PASS — microphone and platform fixture contracts are reliable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# WEEK OUTPUT CONTRACT:
# Input: synthetic PCM streams representing microphone and Zoom/Meet callbacks.
# Output: PASS/FAIL checks proving contiguous chunks, monotonic UTC timestamps,
#         readable files, normalized audio metadata, and malformed-input rejection.
