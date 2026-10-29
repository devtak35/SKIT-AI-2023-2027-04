"""Dependency-free PCM preprocessing primitives for the audio boundary."""

from __future__ import annotations

import struct


def _decode_pcm16le(pcm_s16le: bytes) -> list[int]:
    if not pcm_s16le or len(pcm_s16le) % 2:
        raise ValueError("PCM16 data must contain complete samples")
    return [int.from_bytes(pcm_s16le[i:i + 2], "little", signed=True) for i in range(0, len(pcm_s16le), 2)]


def _encode_pcm16le(samples: list[int]) -> bytes:
    output = bytearray()
    for value in samples:
        output.extend(struct.pack("<h", max(-32768, min(32767, int(value)))))
    return bytes(output)


def normalize_pcm16le(pcm_s16le: bytes, *, target_peak: float = 0.95) -> bytes:
    """Peak-normalize PCM16 without amplifying digital silence."""
    if not pcm_s16le or len(pcm_s16le) % 2:
        raise ValueError("PCM16 data must contain complete samples")
    if not 0 < target_peak <= 1:
        raise ValueError("target_peak must be between 0 and 1")
    samples = _decode_pcm16le(pcm_s16le)
    peak = max(abs(value) for value in samples)
    if peak == 0:
        return pcm_s16le
    scale = target_peak * 32767 / peak
    output = bytearray()
    for value in samples:
        normalized = max(-32768, min(32767, round(value * scale)))
        output.extend(struct.pack("<h", normalized))
    return bytes(output)


def remove_dc_offset(pcm_s16le: bytes) -> bytes:
    """Remove the mean sample offset while preserving PCM16 bounds."""
    if not pcm_s16le or len(pcm_s16le) % 2:
        raise ValueError("PCM16 data must contain complete samples")
    samples = _decode_pcm16le(pcm_s16le)
    offset = round(sum(samples) / len(samples))
    output = bytearray()
    for value in samples:
        output.extend(struct.pack("<h", max(-32768, min(32767, value - offset))))
    return bytes(output)


def suppress_low_level_noise(pcm_s16le: bytes, *, threshold: float = 0.02) -> bytes:
    """Apply a conservative sample-level noise gate.

    This is intentionally deterministic and dependency-free. It is useful for
    fixture and edge-device preprocessing, but it is not a replacement for a
    learned denoiser. Samples below ``threshold`` are muted; louder speech is
    preserved for the ASR provider.
    """
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    samples = _decode_pcm16le(pcm_s16le)
    cutoff = round(threshold * 32768)
    return _encode_pcm16le([0 if abs(value) < cutoff else value for value in samples])


def prepare_pcm_for_asr(
    pcm_s16le: bytes,
    *,
    noise_threshold: float = 0.02,
    target_peak: float = 0.95,
) -> bytes:
    """Run the explainable preprocessing sequence used before ASR.

    DC removal comes first, then a conservative noise gate, then peak
    normalization. This keeps silence silent and makes quiet fixture signals
    comparable without introducing a provider-specific dependency.
    """
    centered = remove_dc_offset(pcm_s16le)
    gated = suppress_low_level_noise(centered, threshold=noise_threshold)
    return normalize_pcm16le(gated, target_peak=target_peak)
