"""ASR and prosody confidence (SPEC §4.6.2)."""

from __future__ import annotations

from typing import Iterable, Optional

from .types import Word


def asr_confidence(
    words: Iterable[Word],
    *,
    transcribed_duration_s: float,
    expected_speech_duration_s: float,
) -> float:
    """ASR-based confidence.

    Definition: mean word probability in scope × coverage
    (share of the expected speech duration transcribed). SPEC §4.6.2.
    Units: unitless ratio in [0, 1].
    Source: heuristic (H).
    Failure modes: empty transcript → 0; expected duration ≤ 0 → coverage 0.
    """
    items = list(words)
    if not items or expected_speech_duration_s <= 0:
        return 0.0
    mean_prob = sum(max(0.0, min(1.0, w.probability)) for w in items) / len(items)
    coverage = min(1.0, max(0.0, transcribed_duration_s / expected_speech_duration_s))
    return max(0.0, min(1.0, mean_prob * coverage))


def snr_factor(snr_db: Optional[float]) -> float:
    """Map SNR to the §4.6.2 factor: 10 dB → 0.3, 20 dB → 1.0, linear (H)."""
    if snr_db is None:
        return 0.0
    if snr_db <= 10.0:
        return 0.3
    if snr_db >= 20.0:
        return 1.0
    return 0.3 + (snr_db - 10.0) / 10.0 * 0.7


def prosody_confidence(
    *,
    voiced_ratio: float,
    snr_db: Optional[float],
    octave_error_ratio: float = 0.0,
) -> float:
    """Prosody confidence.

    Definition: voiced-frame ratio × SNR factor × (1 − octave-error ratio).
    SNR factor is 10 dB → 0.3, 20 dB → 1.0, linear (H). SPEC §4.6.2.
    Units: unitless ratio in [0, 1].
    Source: heuristic (H).
    Failure modes: missing SNR → 0; octave-error ratio ≥ 1 → 0.
    """
    voiced = max(0.0, min(1.0, voiced_ratio))
    octave = max(0.0, min(1.0, octave_error_ratio))
    return max(0.0, min(1.0, voiced * snr_factor(snr_db) * (1.0 - octave)))
