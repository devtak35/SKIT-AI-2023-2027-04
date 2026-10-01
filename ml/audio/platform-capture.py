"""
Week 03 (24-08-2026 - 30-08-2026)
Task: Add Zoom/Meet integration for platform-based capture

Why this matters:
Platform integrations can provide meeting-scoped audio when browser or native
system capture is unavailable. This adapter keeps Zoom/Meet SDK details at the
edge and emits the same ordered PCM chunk contract that Week 2 established for
the ASR stage.

What this script does:
Defines a provider-neutral platform capture adapter, a mock meeting event
source for local testing, and a CLI demonstration that normalizes platform
audio into the existing audio-chunk envelope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import argparse
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
from typing import Iterable, Iterator

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.audio.capture import AudioChunk, make_audio_chunks


@dataclass(frozen=True)
class PlatformAudioEvent:
    """Audio callback shape that a Zoom or Meet connector must provide."""

    meeting_id: str
    pcm_s16le: bytes
    captured_at: datetime
    sequence: int
    provider: str


class PlatformCaptureAdapter:
    """Normalize provider callbacks into the shared ASR audio-chunk contract."""

    def __init__(self, *, session_id: str, chunk_directory: Path, source: str):
        if not session_id:
            raise ValueError("session_id must not be empty")
        if source not in {"zoom", "google_meet"}:
            raise ValueError("source must be 'zoom' or 'google_meet'")
        self.session_id = session_id
        self.chunk_directory = Path(chunk_directory)
        self.source = source

    def ingest(self, event: PlatformAudioEvent) -> list[AudioChunk]:
        """Persist one provider callback and return normalized one-second chunks."""
        if event.provider != self.source:
            raise ValueError("event provider does not match adapter source")
        if not event.meeting_id:
            raise ValueError("meeting_id must not be empty")
        return make_audio_chunks(
            event.pcm_s16le,
            session_id=self.session_id,
            chunk_directory=self.chunk_directory / f"{event.meeting_id}_{event.sequence:04d}",
            captured_at=event.captured_at,
            source=self.source,
        )


def mock_platform_events(
    *, provider: str, meeting_id: str, pcm_s16le: bytes, started_at: datetime
) -> Iterator[PlatformAudioEvent]:
    """Yield deterministic callbacks shaped like a platform SDK audio stream."""
    if len(pcm_s16le) == 0:
        raise ValueError("mock audio must not be empty")
    yield PlatformAudioEvent(
        meeting_id=meeting_id,
        pcm_s16le=pcm_s16le,
        captured_at=started_at,
        sequence=0,
        provider=provider,
    )


def demo(provider: str) -> list[dict[str, object]]:
    """Run the adapter with two seconds of silent 16 kHz mono PCM."""
    session_id = "12345678-1234-5678-1234-567812345678"
    pcm = struct.pack("<32000h", *([0] * 32000))
    started_at = datetime(2026, 8, 24, 9, 0, tzinfo=timezone.utc)
    with TemporaryDirectory(prefix="platform-capture-") as directory:
        adapter = PlatformCaptureAdapter(
            session_id=session_id,
            chunk_directory=Path(directory),
            source=provider,
        )
        chunks: list[AudioChunk] = []
        for event in mock_platform_events(
            provider=provider,
            meeting_id="demo-meeting",
            pcm_s16le=pcm,
            started_at=started_at,
        ):
            chunks.extend(adapter.ingest(event))
        return [chunk.to_event() for chunk in chunks]


def main() -> None:
    parser = argparse.ArgumentParser(description="Demonstrate platform audio normalization.")
    parser.add_argument("--provider", choices=("zoom", "google_meet"), default="zoom")
    args = parser.parse_args()
    print(json.dumps(demo(args.provider), indent=2))


if __name__ == "__main__":
    main()


# WEEK OUTPUT CONTRACT:
# Input: PlatformAudioEvent callbacks containing meeting-scoped PCM audio.
# Output: Week 2-compatible audio events with source="zoom" or "google_meet",
#         ordered sequence values, UTC timestamps, and ASR-readable audio_ref paths.
