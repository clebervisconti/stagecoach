"""Tests for the audio-features stage (issue #24, SPEC §6.4)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.stages.audio_features import (
    classify_pause_position,
    extract_audio_features,
    hz_to_semitones,
    pause_kind,
    remove_octave_jumps,
)


def _write_wav(path: Path, y: np.ndarray, sr: int = 16000) -> Path:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), y.astype(np.float32), sr)
    return path


def sine(freq_hz: float, duration_s: float, sr: int = 16000, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(sr * duration_s)) / sr
    return (amp * np.sin(2 * np.pi * freq_hz * t)).astype(np.float64)


def chirp(f0: float, f1: float, duration_s: float, sr: int = 16000, amp: float = 0.3) -> np.ndarray:
    n = int(sr * duration_s)
    t = np.arange(n) / sr
    k = (f1 - f0) / duration_s
    phase = 2 * np.pi * (f0 * t + 0.5 * k * t * t)
    return (amp * np.sin(phase)).astype(np.float64)


class TestOctaveJumpsAndSemitones:
    def test_removes_jumps_over_10_st(self):
        f0 = np.array([100.0, 100.0, 220.0, 100.0])  # 100→220 is ~13.6 st
        cleaned, ratio = remove_octave_jumps(f0)
        assert np.isnan(cleaned[2])
        assert cleaned[0] == pytest.approx(100.0)
        assert cleaned[3] == pytest.approx(100.0)
        assert ratio > 0

    def test_keeps_small_movements(self):
        f0 = np.array([200.0, 210.0, 190.0, 205.0])
        cleaned, ratio = remove_octave_jumps(f0)
        assert np.all(np.isfinite(cleaned))
        assert ratio == 0.0

    def test_semitones_are_speaker_relative(self):
        f0 = np.array([110.0, 220.0, np.nan])
        st = hz_to_semitones(f0, median_f0=110.0)
        assert st[0] == pytest.approx(0.0)
        assert st[1] == pytest.approx(12.0)
        assert np.isnan(st[2])


class TestPauseClassification:
    def test_kind_boundaries(self):
        assert pause_kind(0.3) == "short"
        assert pause_kind(0.8) == "medium"
        assert pause_kind(3.2) == "long"

    def test_boundary_at_punctuated_segment_end(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello everyone."},
            {"start": 2.8, "end": 5.0, "text": "Next point."},
        ]
        assert classify_pause_position(2.0, 2.8, segments) == "boundary"

    def test_mid_sentence_inside_segment(self):
        segments = [{"start": 0.0, "end": 5.0, "text": "This is one long stretch"}]
        assert classify_pause_position(1.5, 2.2, segments) == "mid_sentence"

    def test_unknown_without_transcript(self):
        assert classify_pause_position(1.0, 1.8, []) == "unknown"


class TestSineSweepF0AndPvq:
    def test_constant_sine_f0_and_low_pvq(self, tmp_path: Path):
        wav = _write_wav(tmp_path / "sine220.wav", sine(220.0, 12.0))
        result = extract_audio_features(wav, tmp_path / "out", session_id="sine220")
        metrics = result.metrics
        assert metrics["median_f0_hz"] == pytest.approx(220.0, rel=0.08)
        assert metrics["voiced_s"] > 8.0
        assert metrics["pvq_median"] is not None
        assert metrics["pvq_median"] < 0.05
        assert metrics["pitch_floor_hz"] < 220.0
        assert metrics["pitch_ceiling_hz"] > 220.0

    def test_chirp_has_rising_f0_and_higher_pvq(self, tmp_path: Path):
        wav = _write_wav(tmp_path / "chirp.wav", chirp(150.0, 350.0, 12.0))
        result = extract_audio_features(wav, tmp_path / "out", session_id="chirp")
        metrics = result.metrics
        assert metrics["median_f0_hz"] is not None
        assert 140.0 < metrics["median_f0_hz"] < 360.0
        assert metrics["pvq_median"] is not None
        assert metrics["pvq_median"] > 0.08

        import pyarrow.parquet as pq

        table = pq.read_table(result.artifacts["prosody"])
        f0 = table.column("f0_hz").to_numpy()
        voiced = f0[np.isfinite(f0)]
        third = max(1, voiced.size // 3)
        assert float(np.median(voiced[:third])) < float(np.median(voiced[-third:]))


class TestArtifactsAndQuality:
    def test_writes_four_artifacts(self, tmp_path: Path):
        wav = _write_wav(tmp_path / "tone.wav", sine(180.0, 4.0))
        result = extract_audio_features(wav, tmp_path / "out", session_id="arts")
        for key in ("prosody", "pauses", "syllables", "audio_metrics"):
            path = Path(result.artifacts[key])
            assert path.exists(), key
        metrics = json.loads(Path(result.artifacts["audio_metrics"]).read_text())
        assert metrics["basis"]["source_keys"] == ["S24", "S25", "S45"]
        assert metrics["basis"]["pvq"] == "research"

        import pyarrow.parquet as pq

        cols = set(pq.read_table(result.artifacts["prosody"]).column_names)
        assert {"time_s", "f0_hz", "f0_st", "voiced", "intensity_db"} <= cols

    def test_pause_in_silence_gap(self, tmp_path: Path):
        sr = 16000
        y = np.concatenate([sine(200.0, 1.0, sr), np.zeros(int(sr * 0.9)), sine(200.0, 1.0, sr)])
        wav = _write_wav(tmp_path / "gap.wav", y, sr)
        transcript = tmp_path / "transcript.json"
        transcript.write_text(
            json.dumps(
                {
                    "segments": [
                        {"start": 0.0, "end": 1.0, "text": "First phrase."},
                        {"start": 1.9, "end": 2.9, "text": "Second phrase."},
                    ]
                }
            )
        )
        result = extract_audio_features(
            wav, tmp_path / "out", session_id="gap", transcript_path=transcript
        )
        pauses = json.loads(Path(result.artifacts["pauses"]).read_text())["pauses"]
        medium_or_long = [p for p in pauses if p["duration"] >= 0.5]
        assert medium_or_long, pauses
        assert any(p["position"] == "boundary" for p in medium_or_long)

    def test_white_noise_sets_noise_flag_and_snr_feeds_confidence(self, tmp_path: Path):
        rng = np.random.default_rng(0)
        noise = 0.2 * rng.standard_normal(16000 * 3)
        wav = _write_wav(tmp_path / "noise.wav", noise)
        result = extract_audio_features(wav, tmp_path / "out", session_id="noise")
        metrics = result.metrics
        assert metrics["noise_flag"] is True
        assert metrics["music_flag"] is False
        assert metrics["confidence"]["snr_below_15db"] is True
        assert metrics["confidence"]["inclusion_cap"] <= 0.5

    def test_clean_sine_has_higher_snr_than_noisy_sine(self, tmp_path: Path):
        rng = np.random.default_rng(1)
        sr = 16000
        tone = sine(180.0, 1.0, sr)
        gap = np.zeros(int(sr * 0.8))
        clean = np.concatenate([tone, gap, tone, gap, tone])
        noisy = clean + 0.12 * rng.standard_normal(clean.size)
        clean_r = extract_audio_features(
            _write_wav(tmp_path / "clean.wav", clean, sr), tmp_path / "c", session_id="c"
        )
        noisy_r = extract_audio_features(
            _write_wav(tmp_path / "noisy.wav", noisy, sr), tmp_path / "n", session_id="n"
        )
        assert clean_r.metrics["snr_db"] > noisy_r.metrics["snr_db"]
