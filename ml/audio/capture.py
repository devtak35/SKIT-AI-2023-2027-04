"""Local microphone capture with a versioned audio-chunk handoff."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
import struct
import uuid
import wave
from typing import Iterable


SAMPLE_RATE_HZ = 16_000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_DURATION_MS = 1_000


@dataclass(frozen=True)
class AudioChunk:
    """One mono PCM chunk and the metadata ASR needs to consume it."""

    event_id: str
    session_id: str
    chunk_id: str
    sequence: int
    captured_at: str
    duration_ms: int
    sample_rate_hz: int
    channels: int
    encoding: str
    source: str
    audio_ref: str
    pcm_s16le: bytes

    def to_event(self) -> dict[str, object]:
        """Return a JSON-ready event envelope without embedding raw audio bytes."""
        return {
            "schema_version": "1.0",
            "event_id": self.event_id,
            "session_id": self.session_id,
            "created_at": self.captured_at,
            "payload": {
                "chunk_id": self.chunk_id,
                "source": self.source,
                "sequence": self.sequence,
                "captured_at": self.captured_at,
                "sample_rate_hz": self.sample_rate_hz,
                "channels": self.channels,
                "encoding": self.encoding,
                "duration_ms": self.duration_ms,
                "audio_ref": self.audio_ref,
            },
        }


def float_samples_to_pcm16le(samples: Iterable[float]) -> bytes:
    """Convert normalized float samples to signed 16-bit little-endian PCM."""
    packed = bytearray()
    for sample in samples:
        clipped = max(-1.0, min(1.0, float(sample)))
        integer = round(clipped * (32768 if clipped < 0 else 32767))
        packed.extend(struct.pack("<h", integer))
    return bytes(packed)


def make_audio_chunks(
    pcm_s16le: bytes,
    *,
    session_id: str,
    chunk_directory: Path,
    captured_at: datetime,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    channels: int = CHANNELS,
    chunk_duration_ms: int = CHUNK_DURATION_MS,
    source: str = "microphone",
) -> list[AudioChunk]:
    """Write chunk files and create event metadata; usable with real or fixture PCM."""
    if sample_rate_hz <= 0 or channels <= 0 or chunk_duration_ms <= 0:
        raise ValueError("sample rate, channel count, and chunk duration must be positive")
    if not pcm_s16le:
        raise ValueError("audio data must not be empty")
    if captured_at.tzinfo is None:
        raise ValueError("captured_at must include a timezone")
    session_id = str(uuid.UUID(session_id))
    frame_bytes = channels * BYTES_PER_SAMPLE
    if len(pcm_s16le) % frame_bytes:
        raise ValueError("PCM byte length must contain complete audio frames")

    chunk_directory.mkdir(parents=True, exist_ok=True)
    target_bytes = sample_rate_hz * channels * BYTES_PER_SAMPLE * chunk_duration_ms // 1000
    target_bytes = max(frame_bytes, target_bytes - target_bytes % frame_bytes)
    normalized_start = captured_at.astimezone(timezone.utc)
    chunks: list[AudioChunk] = []

    for sequence, offset in enumerate(range(0, len(pcm_s16le), target_bytes)):
        payload = pcm_s16le[offset : offset + target_bytes]
        frames = len(payload) // frame_bytes
        duration_ms = round(frames * 1000 / sample_rate_hz)
        chunk_start = normalized_start + timedelta(milliseconds=round(offset / frame_bytes * 1000 / sample_rate_hz))
        chunk_id = str(uuid.uuid4())
        event_id = str(uuid.uuid4())
        chunk_path = chunk_directory / f"{session_id}_{sequence:04d}.pcm"
        chunk_path.write_bytes(payload)
        chunks.append(
            AudioChunk(
                event_id=event_id,
                session_id=session_id,
                chunk_id=chunk_id,
                sequence=sequence,
                captured_at=chunk_start.isoformat().replace("+00:00", "Z"),
                duration_ms=duration_ms,
                sample_rate_hz=sample_rate_hz,
                channels=channels,
                encoding="pcm_s16le",
                source=source,
                audio_ref=str(chunk_path),
                pcm_s16le=payload,
            )
        )
    return chunks


def capture_microphone(
    output_wav: Path,
    *,
    duration_seconds: float,
    session_id: str | None = None,
    device: int | str | None = None,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
    chunk_duration_ms: int = CHUNK_DURATION_MS,
) -> list[AudioChunk]:
    """Record a mono microphone clip, save WAV and chunk files, and return events."""
    if duration_seconds <= 0:
        raise ValueError("duration_seconds must be positive")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if chunk_duration_ms <= 0:
        raise ValueError("chunk_duration_ms must be positive")

    try:
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(
            "Microphone capture requires the audio dependencies in ml/audio/requirements.txt"
        ) from exc

    session_id = str(uuid.UUID(session_id)) if session_id else str(uuid.uuid4())
    frame_count = math.ceil(duration_seconds * sample_rate_hz)
    started_at = datetime.now(timezone.utc)
    recorded = sd.rec(
        frame_count,
        samplerate=sample_rate_hz,
        channels=CHANNELS,
        dtype="float32",
        device=device,
        blocking=True,
    )
    pcm_data = float_samples_to_pcm16le(recorded.reshape(-1).tolist())

    output_wav = Path(output_wav)
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output_wav), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(BYTES_PER_SAMPLE)
        wav_file.setframerate(sample_rate_hz)
        wav_file.writeframes(pcm_data)

    return make_audio_chunks(
        pcm_data,
        session_id=session_id,
        chunk_directory=output_wav.parent / f"{output_wav.stem}_chunks",
        captured_at=started_at,
        sample_rate_hz=sample_rate_hz,
        channels=CHANNELS,
        chunk_duration_ms=chunk_duration_ms,
        source="microphone",
    )
