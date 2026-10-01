"""
Week 02 (17-08-2026 - 23-08-2026)
Task: Build the initial local audio capture module

Why this matters:
Capture is the first live stage and must hand downstream ASR ordered, timestamped audio without binding ASR to a particular device API. This first implementation records local microphone audio; system-loopback adapters remain platform-specific follow-up work.

What this script does:
Exposes the microphone capture implementation and provides a small command-line entry point that writes a WAV clip and prints its audio-chunk event metadata.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ml.audio.capture import capture_microphone, float_samples_to_pcm16le, make_audio_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture a local microphone clip for ASR.")
    parser.add_argument("output", type=Path, help="path for the captured WAV file")
    parser.add_argument("--duration", type=float, default=5.0, help="recording length in seconds")
    parser.add_argument("--device", help="optional sounddevice input device name or numeric index")
    args = parser.parse_args()
    device: int | str | None = args.device
    if isinstance(device, str) and device.isdecimal():
        device = int(device)

    chunks = capture_microphone(args.output, duration_seconds=args.duration, device=device)
    print(json.dumps([chunk.to_event() for chunk in chunks], indent=2))


if __name__ == "__main__":
    main()
