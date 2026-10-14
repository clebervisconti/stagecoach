"""Tiny synthetic WAV writers. Not personal recordings."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def write_sine_wav(
    path: Path,
    *,
    duration_s: float = 1.0,
    freq_hz: float = 440.0,
    sample_rate: int = 16000,
    noise: float = 0.0,
) -> int:
    """Write a mono 16-bit PCM sine. `noise` is a deterministic mix in [0, 1]."""
    path.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, int(duration_s * sample_rate))
    frames = bytearray()
    for i in range(n):
        t = i / sample_rate
        value = math.sin(2 * math.pi * freq_hz * t)
        if noise:
            # Linear congruential noise so the file is reproducible.
            pseudo = ((i * 1103515245 + 12345) % 2**31) / 2**31
            value += noise * (pseudo * 2 - 1)
        sample = int(max(-1.0, min(1.0, value)) * 32767)
        frames += struct.pack("<h", sample)
    with wave.open(str(path), "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(frames)
    return path.stat().st_size


def read_wav_meta(path: Path) -> dict[str, int | float]:
    with wave.open(str(path), "r") as wav:
        rate = wav.getframerate()
        frames = wav.getnframes()
        return {
            "channels": wav.getnchannels(),
            "sample_width": wav.getsampwidth(),
            "sample_rate": rate,
            "duration_s": frames / rate if rate else 0.0,
            "frames": frames,
        }
