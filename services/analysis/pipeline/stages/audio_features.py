"""Audio-features stage: F0, PVQ, intensity, syllables, pauses, SNR.

Per SPEC §6.4, §4.4.9, §4.4.10 and issue #24.
Prosody is computed on the un-normalized analysis audio (audio16k.wav).
Parselmouth/Praat stays server-side only (ADR-013, GPL-3.0-or-later).
"""

from __future__ import annotations

import json
import logging
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"
TIME_STEP_S = 0.010  # 10 ms tracks in prosody.parquet

# Two-pass F0 limits — common heuristic (H), SPEC §6.4
FIRST_PASS_FLOOR_HZ = 75.0
FIRST_PASS_CEILING_HZ = 600.0
ADAPT_Q_LOW = 0.15
ADAPT_Q_HIGH = 0.65
ADAPT_FLOOR_MULT = 0.83
ADAPT_CEIL_MULT = 1.92
OCTAVE_JUMP_ST = 10.0
OCTAVE_JUMP_RERUN_RATIO = 0.05  # §4.4.10 confidence check (H)

# PVQ windows — Hincks [S24]
PVQ_WINDOW_S = 10.0
PVQ_MIN_VOICED_S = 3.0
MONOTONE_PVQ = 0.08
MONOTONE_RANGE_ST = 3.0

# Pauses — §4.4.9
MIN_PAUSE_S = 0.250
BOUNDARY_PAUSE_MIN_S = 0.5
BOUNDARY_PAUSE_MAX_S = 2.0
LONG_PAUSE_S = 3.0

# de Jong & Wempe [S25] syllable nuclei (Praat-script defaults, H)
SYLLABLE_MIN_DIP_DB = 2.0
SYLLABLE_SILENCE_DB = 25.0
SYLLABLE_MIN_PAUSE_S = 0.30

# Confidence / quality — §4.4.10 (H)
SNR_CONFIDENCE_CAP_DB = 15.0
NOISE_FLATNESS_THRESHOLD = 0.35
NOISE_MAX_VOICED_RATIO = 0.25
MUSIC_MIN_DURATION_S = 8.0
MUSIC_MAX_PVQ = 0.03
MUSIC_MAX_INTENSITY_SD_DB = 2.0

SENTENCE_END_RE = re.compile(r"[.!?…]\s*$")


@dataclass
class Pause:
    start: float
    end: float
    duration: float
    kind: str
    position: str  # boundary | mid_sentence | unknown

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "duration": round(self.duration, 3),
            "kind": self.kind,
            "position": self.position,
        }


@dataclass
class SyllableNucleus:
    time: float
    intensity_db: float

    def to_dict(self) -> Dict[str, Any]:
        return {"time": round(self.time, 3), "intensity_db": round(self.intensity_db, 2)}


@dataclass
class AudioFeaturesOutput:
    session_id: str
    stage_version: str
    artifacts: Dict[str, str]
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "stage_version": self.stage_version,
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }


def hz_to_semitones(f0_hz: np.ndarray, median_f0: float) -> np.ndarray:
    """Speaker-relative semitones: 12·log2(f0 / median_f0). Never scores absolute pitch."""
    out = np.full_like(f0_hz, np.nan, dtype=float)
    if median_f0 <= 0 or not np.isfinite(median_f0):
        return out
    voiced = np.isfinite(f0_hz) & (f0_hz > 0)
    out[voiced] = 12.0 * np.log2(f0_hz[voiced] / median_f0)
    return out


def remove_octave_jumps(f0_hz: np.ndarray, max_st: float = OCTAVE_JUMP_ST) -> Tuple[np.ndarray, float]:
    """Unvoice frames that jump more than max_st from the previous voiced frame.

    Returns (cleaned_f0, jump_ratio_before_cleaning among consecutive voiced pairs).
    """
    cleaned = f0_hz.astype(float).copy()
    jumps = 0
    pairs = 0
    last_voiced: Optional[float] = None
    for i, val in enumerate(cleaned):
        if not (np.isfinite(val) and val > 0):
            continue
        if last_voiced is not None:
            pairs += 1
            st = abs(12.0 * math.log2(val / last_voiced))
            if st > max_st:
                jumps += 1
                cleaned[i] = np.nan
                continue
        last_voiced = val
    ratio = (jumps / pairs) if pairs else 0.0
    return cleaned, ratio


def adaptive_pitch_limits(voiced_f0: np.ndarray) -> Tuple[float, float]:
    """Speaker-adaptive floor/ceiling from first-pass voiced F0 (H, §6.4)."""
    if voiced_f0.size < 10:
        return FIRST_PASS_FLOOR_HZ, FIRST_PASS_CEILING_HZ
    q15 = float(np.quantile(voiced_f0, ADAPT_Q_LOW))
    q65 = float(np.quantile(voiced_f0, ADAPT_Q_HIGH))
    floor = max(50.0, q15 * ADAPT_FLOOR_MULT)
    ceiling = min(800.0, max(floor + 50.0, q65 * ADAPT_CEIL_MULT))
    return floor, ceiling


def _pitch_to_arrays(pitch) -> Tuple[np.ndarray, np.ndarray]:
    times = np.asarray(pitch.xs(), dtype=float)
    freq = np.asarray(pitch.selected_array["frequency"], dtype=float)
    freq[freq <= 0] = np.nan
    return times, freq


def extract_f0_two_pass(sound) -> Tuple[np.ndarray, np.ndarray, float, float, float]:
    """Two-pass Praat autocorrelation F0 with octave-jump cleanup.

    Returns times, f0_hz, floor, ceiling, octave_jump_ratio.
    """
    pitch1 = sound.to_pitch_ac(
        time_step=TIME_STEP_S,
        pitch_floor=FIRST_PASS_FLOOR_HZ,
        pitch_ceiling=FIRST_PASS_CEILING_HZ,
    )
    _times1, f0_1 = _pitch_to_arrays(pitch1)
    voiced = f0_1[np.isfinite(f0_1)]
    floor, ceiling = adaptive_pitch_limits(voiced)

    pitch2 = sound.to_pitch_ac(
        time_step=TIME_STEP_S,
        pitch_floor=floor,
        pitch_ceiling=ceiling,
    )
    times, f0 = _pitch_to_arrays(pitch2)
    cleaned, jump_ratio = remove_octave_jumps(f0)

    if jump_ratio > OCTAVE_JUMP_RERUN_RATIO and voiced.size >= 10:
        tighter_ceiling = min(ceiling, float(np.quantile(voiced, 0.90)) * 1.5)
        pitch3 = sound.to_pitch_ac(
            time_step=TIME_STEP_S,
            pitch_floor=floor,
            pitch_ceiling=max(floor + 50.0, tighter_ceiling),
        )
        times, f0 = _pitch_to_arrays(pitch3)
        cleaned, jump_ratio = remove_octave_jumps(f0)
        ceiling = max(floor + 50.0, tighter_ceiling)

    return times, cleaned, floor, ceiling, jump_ratio


def extract_intensity(sound, times: np.ndarray) -> np.ndarray:
    """Praat intensity (dB) interpolated onto the 10 ms F0 grid."""
    intensity = sound.to_intensity(minimum_pitch=FIRST_PASS_FLOOR_HZ, time_step=TIME_STEP_S)
    i_times = np.asarray(intensity.xs(), dtype=float)
    i_vals = np.asarray(intensity.values[0], dtype=float)
    if i_times.size == 0:
        return np.full(times.shape, np.nan)
    return np.interp(times, i_times, i_vals, left=np.nan, right=np.nan)


def window_series(
    times: np.ndarray,
    values: np.ndarray,
    window_s: float,
    hop_s: float,
    min_valid_s: float,
    fn,
) -> List[Dict[str, Any]]:
    """Apply fn to valid samples in sliding windows. fn receives a 1-d array."""
    if times.size == 0:
        return []
    duration = float(times[-1] - times[0])
    if duration <= 0:
        return []
    out: List[Dict[str, Any]] = []
    start = float(times[0])
    end_limit = float(times[-1])
    while start + min_valid_s <= end_limit + 1e-9:
        stop = start + window_s
        mask = (times >= start) & (times < stop) & np.isfinite(values)
        valid_s = float(np.count_nonzero(mask)) * TIME_STEP_S
        if valid_s >= min_valid_s:
            stat = fn(values[mask])
            if stat is not None and np.isfinite(stat):
                out.append(
                    {
                        "start": round(start, 3),
                        "end": round(min(stop, end_limit), 3),
                        "value": float(stat),
                        "voiced_s": round(valid_s, 3),
                    }
                )
        start += hop_s
    return out


def compute_pvq_windows(times: np.ndarray, f0_hz: np.ndarray) -> List[Dict[str, Any]]:
    """PVQ = SD(F0 Hz) / mean(F0 Hz) per 10-s window with ≥ 3 s voiced [S24]."""

    def _pvq(x: np.ndarray) -> Optional[float]:
        if x.size < 2 or float(np.mean(x)) <= 0:
            return None
        return float(np.std(x, ddof=1) / np.mean(x))

    return window_series(times, f0_hz, PVQ_WINDOW_S, 5.0, PVQ_MIN_VOICED_S, _pvq)


def compute_pitch_range_st_windows(times: np.ndarray, f0_st: np.ndarray) -> List[Dict[str, Any]]:
    def _range(x: np.ndarray) -> Optional[float]:
        if x.size < 5:
            return None
        return float(np.nanpercentile(x, 95) - np.nanpercentile(x, 5))

    return window_series(times, f0_st, PVQ_WINDOW_S, 5.0, PVQ_MIN_VOICED_S, _range)


def monotone_windows_ratio(pvq_windows: List[Dict[str, Any]], range_windows: List[Dict[str, Any]]) -> float:
    """Share of overlapping 10-s windows that are monotone (proxy for 30-s rule when short)."""
    if not pvq_windows or not range_windows:
        return 0.0
    by_start = {w["start"]: w["value"] for w in range_windows}
    flags = []
    for w in pvq_windows:
        rng = by_start.get(w["start"])
        if rng is None:
            continue
        flags.append(w["value"] < MONOTONE_PVQ and rng < MONOTONE_RANGE_ST)
    if not flags:
        return 0.0
    return float(sum(flags) / len(flags))


def energy_vad(y: np.ndarray, sr: int, min_pause_s: float = MIN_PAUSE_S) -> Tuple[np.ndarray, np.ndarray, List[Tuple[float, float]]]:
    """Frame-energy VAD. Returns frame times, speech mask, and pause (start, end) pairs.

    Silero VAD arrives with WhisperX alignment (#21). This energy VAD is the
    standalone fallback so the stage can run without gated models.
    """
    frame = int(sr * 0.020)
    hop = int(sr * 0.010)
    if y.size < frame:
        return np.array([]), np.array([], dtype=bool), []

    n_frames = 1 + max(0, (y.size - frame) // hop)
    rms = np.empty(n_frames, dtype=float)
    for i in range(n_frames):
        sl = y[i * hop : i * hop + frame]
        rms[i] = float(np.sqrt(np.mean(sl.astype(float) ** 2) + 1e-12))
    times = (np.arange(n_frames) * hop + frame / 2) / sr
    db = 20.0 * np.log10(rms + 1e-12)
    # Threshold: 30th percentile of frames above absolute silence, minus a small margin
    audible = db > -60.0
    if not np.any(audible):
        return times, np.zeros(n_frames, dtype=bool), [(0.0, float(y.size / sr))]
    thresh = float(np.percentile(db[audible], 25)) - 3.0
    speech = db >= thresh

    pauses: List[Tuple[float, float]] = []
    in_pause = False
    p_start = 0.0
    for i, is_speech in enumerate(speech):
        t = float(times[i])
        if not is_speech and not in_pause:
            in_pause = True
            p_start = t
        elif is_speech and in_pause:
            in_pause = False
            if t - p_start >= min_pause_s:
                pauses.append((p_start, t))
    if in_pause:
        end = float(y.size / sr)
        if end - p_start >= min_pause_s:
            pauses.append((p_start, end))
    return times, speech, pauses


def pause_kind(duration: float) -> str:
    if duration >= LONG_PAUSE_S:
        return "long"
    if duration >= BOUNDARY_PAUSE_MIN_S:
        return "medium"
    return "short"


def classify_pause_position(
    start: float,
    end: float,
    segments: List[Dict[str, Any]],
) -> str:
    """boundary vs mid_sentence using ASR punctuation and segment edges (§6.4)."""
    if not segments:
        return "unknown"

    # Pause sits between two segments (or at a punctuated segment end).
    for i, seg in enumerate(segments):
        s0 = float(seg.get("start", 0.0))
        s1 = float(seg.get("end", 0.0))
        text = str(seg.get("text") or "")
        if s0 - 0.15 <= start <= s1 + 0.15 and s0 - 0.15 <= end <= s1 + 0.15:
            return "mid_sentence"
        if abs(start - s1) <= 0.35 or (s1 <= start and (i + 1 >= len(segments) or end <= float(segments[i + 1].get("start", end)) + 0.35)):
            if SENTENCE_END_RE.search(text.strip()):
                return "boundary"
            next_seg = segments[i + 1] if i + 1 < len(segments) else None
            if next_seg and float(next_seg.get("start", 0.0)) >= start - 0.05:
                return "boundary"
    # First/last trailing silence
    first = float(segments[0].get("start", 0.0))
    last = float(segments[-1].get("end", 0.0))
    if end <= first + 0.2 or start >= last - 0.2:
        return "boundary"
    return "mid_sentence"


def detect_syllable_nuclei(
    times: np.ndarray,
    intensity_db: np.ndarray,
    voiced: np.ndarray,
) -> List[SyllableNucleus]:
    """Port of de Jong & Wempe (2009) [S25]: voiced intensity peaks with a preceding dip."""
    valid = np.isfinite(intensity_db)
    if not np.any(valid):
        return []
    peak_floor = float(np.nanmax(intensity_db)) - SYLLABLE_SILENCE_DB
    nuclei: List[SyllableNucleus] = []
    last_peak_db: Optional[float] = None
    last_peak_t: Optional[float] = None

    for i in range(1, len(intensity_db) - 1):
        if not valid[i] or not voiced[i]:
            continue
        db = float(intensity_db[i])
        if db < peak_floor:
            continue
        if not (db >= float(intensity_db[i - 1]) and db >= float(intensity_db[i + 1])):
            continue
        t = float(times[i])
        if last_peak_db is None:
            nuclei.append(SyllableNucleus(time=t, intensity_db=db))
            last_peak_db = db
            last_peak_t = t
            continue
        # Require a dip of MIN_DIP_DB between peaks and a minimum separation
        lo = min(last_peak_t, t)  # type: ignore[type-var]
        hi = max(last_peak_t, t)  # type: ignore[type-var]
        span = (times >= lo) & (times <= hi) & valid
        if not np.any(span):
            continue
        dip = min(last_peak_db, db) - float(np.nanmin(intensity_db[span]))
        if dip >= SYLLABLE_MIN_DIP_DB and (t - last_peak_t) >= SYLLABLE_MIN_PAUSE_S / 3:
            nuclei.append(SyllableNucleus(time=t, intensity_db=db))
            last_peak_db = db
            last_peak_t = t
    return nuclei


def estimate_snr_db(y: np.ndarray, speech_mask: np.ndarray, hop: int, frame: int) -> float:
    """Speech vs non-speech energy ratio from VAD frames. Feeds confidence (§4.4.10)."""
    if speech_mask.size == 0:
        return 0.0
    speech_e = []
    noise_e = []
    for i, is_speech in enumerate(speech_mask):
        sl = y[i * hop : i * hop + frame]
        if sl.size == 0:
            continue
        e = float(np.mean(sl.astype(float) ** 2))
        (speech_e if is_speech else noise_e).append(e)
    if not speech_e:
        return 0.0
    speech_p = float(np.mean(speech_e))
    noise_p = float(np.mean(noise_e)) if noise_e else speech_p * 1e-4
    return float(10.0 * math.log10((speech_p + 1e-12) / (noise_p + 1e-12)))


def spectral_quality_flags(
    y: np.ndarray,
    sr: int,
    voiced_ratio: float,
    duration_s: float,
    pvq_median: Optional[float],
    intensity_sd: Optional[float],
) -> Tuple[bool, bool, float]:
    """Heuristic music/noise flags from spectral flatness + harmonic stability.

    openSMILE is not used (commercial license, §6.9). Labeled heuristic.
    """
    import librosa

    hop = 512
    flatness = librosa.feature.spectral_flatness(y=y.astype(float), hop_length=hop)
    median_flatness = float(np.median(flatness))
    noise_flag = median_flatness > NOISE_FLATNESS_THRESHOLD and voiced_ratio < NOISE_MAX_VOICED_RATIO
    music_flag = (
        duration_s >= MUSIC_MIN_DURATION_S
        and voiced_ratio >= 0.5
        and pvq_median is not None
        and pvq_median < MUSIC_MAX_PVQ
        and intensity_sd is not None
        and intensity_sd < MUSIC_MAX_INTENSITY_SD_DB
        and not noise_flag
    )
    return music_flag, noise_flag, median_flatness


def load_transcript_segments(transcript_path: Optional[Path]) -> List[Dict[str, Any]]:
    if transcript_path is None or not transcript_path.exists():
        return []
    data = json.loads(transcript_path.read_text())
    return list(data.get("segments") or [])


def _write_parquet(path: Path, columns: Dict[str, np.ndarray]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    arrays = {}
    for name, values in columns.items():
        arrays[name] = np.asarray(values)
    table = pa.table(arrays)
    pq.write_table(table, path)


def extract_audio_features(
    audio_path: Path,
    output_dir: Path,
    session_id: str,
    transcript_path: Optional[Path] = None,
) -> AudioFeaturesOutput:
    """Run the audio-features stage and write the four artifacts from issue #24."""
    import parselmouth
    import soundfile as sf

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    y, sr = sf.read(str(audio_path), always_2d=False)
    if y.ndim > 1:
        y = np.mean(y, axis=1)
    y = y.astype(np.float64)
    duration_s = float(y.size / sr) if sr else 0.0
    sound = parselmouth.Sound(y, sampling_frequency=float(sr))

    times, f0_hz, floor, ceiling, jump_ratio = extract_f0_two_pass(sound)
    intensity_db = extract_intensity(sound, times)
    voiced_mask = np.isfinite(f0_hz) & (f0_hz > 0)
    voiced_f0 = f0_hz[voiced_mask]
    median_f0 = float(np.median(voiced_f0)) if voiced_f0.size else float("nan")
    f0_st = hz_to_semitones(f0_hz, median_f0)
    voiced_s = float(np.count_nonzero(voiced_mask)) * TIME_STEP_S
    voiced_ratio = voiced_s / duration_s if duration_s > 0 else 0.0

    pvq_windows = compute_pvq_windows(times, f0_hz)
    range_windows = compute_pitch_range_st_windows(times, f0_st)
    pvq_median = float(np.median([w["value"] for w in pvq_windows])) if pvq_windows else None
    pitch_range_st_median = (
        float(np.median([w["value"] for w in range_windows])) if range_windows else None
    )
    voiced_intensity = intensity_db[voiced_mask & np.isfinite(intensity_db)]
    if voiced_intensity.size:
        intensity_db = intensity_db - float(np.median(voiced_intensity))
        voiced_intensity = intensity_db[voiced_mask & np.isfinite(intensity_db)]
    intensity_sd = float(np.std(voiced_intensity, ddof=1)) if voiced_intensity.size > 1 else None

    nuclei = detect_syllable_nuclei(times, intensity_db, voiced_mask)
    phonation_s = voiced_s
    articulation_rate = (len(nuclei) / phonation_s) if phonation_s > 0 else 0.0

    frame = int(sr * 0.020)
    hop = int(sr * 0.010)
    _vad_times, speech_mask, raw_pauses = energy_vad(y, sr)
    segments = load_transcript_segments(transcript_path)
    pauses = [
        Pause(
            start=a,
            end=b,
            duration=b - a,
            kind=pause_kind(b - a),
            position=classify_pause_position(a, b, segments),
        )
        for a, b in raw_pauses
    ]
    snr_db = estimate_snr_db(y, speech_mask, hop, frame)
    music_flag, noise_flag, median_flatness = spectral_quality_flags(
        y, sr, voiced_ratio, duration_s, pvq_median, intensity_sd
    )
    # Continuous noise looks like "all speech" to energy VAD; flatness overrides.
    if noise_flag:
        snr_db = min(snr_db, 8.0)

    # Prominence (experimental, §6.4): local maxima of z(F0)+z(intensity)
    emphasis_rate = 0.0
    if voiced_f0.size > 10 and voiced_intensity.size > 10:
        z_f0 = (f0_st - np.nanmean(f0_st)) / (np.nanstd(f0_st) + 1e-9)
        z_i = (intensity_db - np.nanmean(intensity_db)) / (np.nanstd(intensity_db) + 1e-9)
        combo = z_f0 + z_i
        peaks = 0
        for i in range(1, len(combo) - 1):
            if not np.isfinite(combo[i]) or not voiced_mask[i]:
                continue
            if combo[i] > 1.5 and combo[i] >= combo[i - 1] and combo[i] >= combo[i + 1]:
                peaks += 1
        emphasis_rate = peaks / (duration_s / 60.0) if duration_s > 0 else 0.0

    confidence_cap = 1.0
    if snr_db < SNR_CONFIDENCE_CAP_DB:
        confidence_cap = min(confidence_cap, 0.5)
    if voiced_s < 60.0:
        confidence_cap = min(confidence_cap, 0.7)
    if music_flag:
        confidence_cap = 0.0

    metrics: Dict[str, Any] = {
        "version": STAGE_VERSION,
        "duration_s": round(duration_s, 3),
        "sample_rate": int(sr),
        "voiced_s": round(voiced_s, 3),
        "voiced_ratio": round(voiced_ratio, 4),
        "median_f0_hz": None if not np.isfinite(median_f0) else round(median_f0, 2),
        "pitch_floor_hz": round(floor, 2),
        "pitch_ceiling_hz": round(ceiling, 2),
        "octave_jump_ratio": round(jump_ratio, 4),
        "pvq_median": None if pvq_median is None else round(pvq_median, 4),
        "pvq_windows": pvq_windows,
        "pitch_range_st_median": None if pitch_range_st_median is None else round(pitch_range_st_median, 3),
        "monotone_windows_ratio": round(monotone_windows_ratio(pvq_windows, range_windows), 4),
        "intensity_sd_db_median": None if intensity_sd is None else round(intensity_sd, 3),
        "emphasis_rate_per_min": round(emphasis_rate, 3),
        "syllable_count": len(nuclei),
        "phonation_time_s": round(phonation_s, 3),
        "articulation_rate_sps": round(articulation_rate, 3),
        "snr_db": round(snr_db, 2),
        "music_flag": music_flag,
        "noise_flag": noise_flag,
        "spectral_flatness_median": round(median_flatness, 4),
        "pause_counts": {
            "short": sum(1 for p in pauses if p.kind == "short"),
            "medium": sum(1 for p in pauses if p.kind == "medium"),
            "long": sum(1 for p in pauses if p.kind == "long"),
            "boundary": sum(1 for p in pauses if p.position == "boundary"),
            "mid_sentence": sum(1 for p in pauses if p.position == "mid_sentence"),
            "unknown": sum(1 for p in pauses if p.position == "unknown"),
        },
        "confidence": {
            "inclusion_cap": confidence_cap,
            "snr_below_15db": snr_db < SNR_CONFIDENCE_CAP_DB,
            "vocal_variety_na": music_flag,
            "voiced_seconds": round(voiced_s, 3),
        },
        "basis": {
            "f0_two_pass": "heuristic",
            "pvq": "research",
            "syllable_nuclei": "research",
            "pauses": "heuristic",
            "snr_music": "heuristic",
            "source_keys": ["S24", "S25", "S45"],
        },
    }

    prosody_path = output_dir / "prosody.parquet"
    pauses_path = output_dir / "pauses.json"
    syllables_path = output_dir / "syllables.json"
    metrics_path = output_dir / "audio_metrics.json"

    _write_parquet(
        prosody_path,
        {
            "time_s": times,
            "f0_hz": f0_hz,
            "f0_st": f0_st,
            "voiced": voiced_mask.astype(np.int8),
            "intensity_db": intensity_db,
        },
    )
    pauses_path.write_text(
        json.dumps(
            {
                "version": STAGE_VERSION,
                "min_pause_s": MIN_PAUSE_S,
                "pauses": [p.to_dict() for p in pauses],
                "counts": metrics["pause_counts"],
            },
            indent=2,
        )
        + "\n"
    )
    syllables_path.write_text(
        json.dumps(
            {
                "version": STAGE_VERSION,
                "algorithm": "de_jong_wempe_2009",
                "source_key": "S25",
                "nuclei": [n.to_dict() for n in nuclei],
                "count": len(nuclei),
                "phonation_time_s": round(phonation_s, 3),
                "articulation_rate_sps": round(articulation_rate, 3),
            },
            indent=2,
        )
        + "\n"
    )
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")

    logger.info(
        "audio_features session=%s duration=%.1fs voiced=%.1fs pvq=%s snr=%.1f",
        session_id,
        duration_s,
        voiced_s,
        pvq_median,
        snr_db,
    )

    return AudioFeaturesOutput(
        session_id=session_id,
        stage_version=STAGE_VERSION,
        artifacts={
            "prosody": str(prosody_path),
            "pauses": str(pauses_path),
            "syllables": str(syllables_path),
            "audio_metrics": str(metrics_path),
        },
        metrics=metrics,
    )
