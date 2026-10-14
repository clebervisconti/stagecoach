"""Unit tests for Phase 1 metric functions (issue #25) on synthetic inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from metrics.confidence import asr_confidence, prosody_confidence, snr_factor
from metrics.fluency import (
    FILLER_BENCHMARK_HARMFUL,
    FILLER_BENCHMARK_NO_PENALTY,
    combined_filler_rate,
    compute_fluency_metrics,
    filler_benchmark_note,
    fl_filler_sounds_per_min,
)
from metrics.pace import (
    pp_articulation_rate_sps,
    pp_boundary_pause_ratio,
    pp_mean_length_of_run,
    pp_pace_cv,
    pp_rush_index,
    pp_unplanned_long_pauses_per_10min,
    pp_wpm,
)
from metrics.prosody import vv_monotone_windows_ratio, vv_pitch_range_st, vv_pvq_median
from metrics.timing import tm_pct_of_slot, tm_qa_time_protected, tm_section_variance
from metrics.types import PauseEvent, ProsodyFrame, SectionPlan, Word

SCORING_YAML = (
    Path(__file__).resolve().parents[3] / "packages" / "scoring-config" / "v1.0.0" / "scoring.yaml"
)

EXPECTED_UNITS = {
    "pp_wpm": "words_per_minute",
    "pp_articulation_rate_sps": "syllables_per_second",
    "pp_pace_cv": "coefficient_of_variation",
    "pp_rush_index": "ratio",
    "pp_boundary_pause_ratio": "ratio",
    "pp_unplanned_long_pauses_per_10min": "per_10min",
    "pp_mean_length_of_run": "words",
    "vv_pvq_median": "ratio",
    "vv_pitch_range_st": "semitones",
    "vv_monotone_windows_ratio": "ratio",
    "vv_intensity_variation_db": "decibels",
    "vv_emphasis_rate_per_min": "per_minute",
    "fl_filler_sounds_per_min": "per_minute",
    "fl_filler_words_per_min": "per_minute",
    "fl_hedges_apologies_per_10min": "per_10min",
    "fl_repetitions_restarts_per_min": "per_minute",
    "fl_grammar_llm": "llm_level",
    "tm_pct_of_slot": "ratio",
    "tm_section_variance": "mean_abs_pct_deviation",
    "tm_end_rush_events": "count",
    "tm_qa_time_protected": "ratio",
}


def _words_at_wpm(n: int, wpm: float, start: float = 0.0) -> list[Word]:
    interval = 60.0 / wpm
    return [
        Word(text=f"w{i}", start=start + i * interval, end=start + (i + 1) * interval)
        for i in range(n)
    ]


def test_units_match_scoring_yaml():
    config = yaml.safe_load(SCORING_YAML.read_text())
    for category in ("pace_pausing", "vocal_variety", "fluency", "time_management"):
        for metric_id, spec in config["categories"][category]["metrics"].items():
            assert metric_id in EXPECTED_UNITS
            assert spec["unit"] == EXPECTED_UNITS[metric_id], (
                f"{metric_id}: code={EXPECTED_UNITS[metric_id]} yaml={spec['unit']}"
            )


def test_pp_wpm_known_rate():
    words = _words_at_wpm(130, 130.0)
    result = pp_wpm(words)
    assert result.unit == "words_per_minute"
    assert result.value == pytest.approx(130.0, abs=0.05)


def test_pp_wpm_excludes_filler_sounds():
    words = _words_at_wpm(60, 60.0) + [Word(text="um", start=61.0, end=61.2)]
    result = pp_wpm(words, filler_sounds=["um"])
    assert result.value == pytest.approx(60.0, abs=0.1)


def test_pp_articulation_rate():
    result = pp_articulation_rate_sps(100, 20.0)
    assert result.unit == "syllables_per_second"
    assert result.value == pytest.approx(5.0)


def test_pp_pace_cv_constant_is_zero():
    words = _words_at_wpm(200, 150.0)  # > 30 s of even pacing
    result = pp_pace_cv(words)
    assert result.unit == "coefficient_of_variation"
    assert result.value == pytest.approx(0.0, abs=0.02)


def test_pp_rush_index_steady_is_one():
    words = _words_at_wpm(200, 140.0)
    result = pp_rush_index(words)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(1.0, rel=0.15)


def test_pp_boundary_pause_ratio():
    pauses = [
        PauseEvent(1.0, 2.0, "boundary"),  # 1.0 s
        PauseEvent(5.0, 5.1, "boundary"),  # too short
    ]
    result = pp_boundary_pause_ratio([1.0, 5.0], pauses)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(0.5)


def test_pp_unplanned_long_pauses_per_10min():
    pauses = [PauseEvent(10.0, 13.5, "mid_sentence"), PauseEvent(20.0, 21.0, "boundary")]
    result = pp_unplanned_long_pauses_per_10min(pauses, speaking_span_s=600.0)
    assert result.unit == "per_10min"
    assert result.value == pytest.approx(1.0)


def test_pp_mean_length_of_run():
    words = [Word(text=f"w{i}", start=float(i), end=float(i) + 0.4) for i in range(6)]
    pauses = [PauseEvent(2.4, 2.8, "unknown")]  # after w2
    result = pp_mean_length_of_run(words, pauses)
    assert result.unit == "words"
    assert result.value == pytest.approx(3.0)


def test_constant_f0_low_pvq():
    frames = [
        ProsodyFrame(t * 0.01, 220.0, 0.0, True, -20.0) for t in range(1200)
    ]
    result = vv_pvq_median(frames)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(0.0, abs=1e-9)


def test_two_tone_f0_known_pvq():
    frames = []
    for t in range(1200):
        hz = 100.0 if t % 2 == 0 else 200.0
        frames.append(ProsodyFrame(t * 0.01, hz, 0.0, True, -20.0))
    # Alternating 100/200 Hz: mean 150, pstdev 50, PVQ = 1/3
    result = vv_pvq_median(frames)
    assert result.applicable
    assert result.value == pytest.approx(50.0 / 150.0, abs=0.01)


def test_constant_pitch_range_zero():
    frames = [ProsodyFrame(t * 0.01, 180.0, 0.0, True, -18.0) for t in range(1200)]
    result = vv_pitch_range_st(frames)
    assert result.unit == "semitones"
    assert result.value == pytest.approx(0.0, abs=1e-9)


def test_monotone_windows_all_flat():
    frames = [ProsodyFrame(t * 0.01, 180.0, 0.0, True, -18.0) for t in range(4000)]
    result = vv_monotone_windows_ratio(frames)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(1.0)


def test_filler_sounds_five_per_minute_benchmark():
    words = [Word(text="hello", start=i * 0.5, end=i * 0.5 + 0.4) for i in range(119)]
    words.append(Word(text="last", start=59.5, end=60.0))
    words += [Word(text="um", start=10.0 + i, end=10.2 + i) for i in range(5)]
    result = fl_filler_sounds_per_min(words, ["um"])
    assert result.unit == "per_minute"
    assert result.value == pytest.approx(5.0, abs=1e-9)
    assert result.value <= FILLER_BENCHMARK_NO_PENALTY


def test_filler_sounds_twelve_per_minute_benchmark():
    words = [Word(text="hello", start=i * 0.4, end=i * 0.4 + 0.3) for i in range(149)]
    words.append(Word(text="last", start=59.6, end=60.0))
    words += [Word(text="um", start=2.0 + i * 4.0, end=2.2 + i * 4.0) for i in range(12)]
    result = fl_filler_sounds_per_min(words, ["um"])
    assert result.value == pytest.approx(12.0, abs=1e-9)
    assert result.value >= FILLER_BENCHMARK_HARMFUL


def test_combined_filler_rate_and_benchmark_note():
    combined = combined_filler_rate(5.0, 0.0)
    assert combined == 5.0
    note = filler_benchmark_note(combined)
    assert note["no_penalty_at_or_below"] == 5.0
    assert note["harmful_at"] == 12.0
    assert note["source"] == "S12"


def test_repetitions_and_hedges():
    words = [
        Word("the", 0.0, 0.2),
        Word("the", 0.2, 0.4),
        Word("plan", 0.4, 0.7),
        Word("is", 0.7, 0.9),
        Word("ready", 0.9, 1.2),
    ]
    # pad span to 60s
    words.append(Word("end", 59.0, 59.5))
    metrics = compute_fluency_metrics(
        words,
        hedges=["i think maybe"],
        apologies=["sorry"],
        transcript_text="I think maybe this is fine. Sorry.",
    )
    assert metrics["fl_repetitions_restarts_per_min"].value == pytest.approx(1.0, abs=0.05)
    assert metrics["fl_hedges_apologies_per_10min"].unit == "per_10min"
    assert metrics["fl_hedges_apologies_per_10min"].value == pytest.approx(20.0, abs=0.2)


def test_tm_pct_of_slot_ninety_percent():
    result = tm_pct_of_slot(540.0, 600.0)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(0.9)


def test_tm_pct_of_slot_without_slot_is_na():
    result = tm_pct_of_slot(100.0, None)
    assert result.applicable is False
    assert result.failure_mode == "slot_length_not_provided"


def test_tm_section_variance():
    sections = [
        SectionPlan("open", 300.0, 240.0),
        SectionPlan("close", 300.0, 360.0),
    ]
    result = tm_section_variance(sections)
    assert result.unit == "mean_abs_pct_deviation"
    assert result.value == pytest.approx(0.2)


def test_tm_qa_time_protected():
    result = tm_qa_time_protected(9.0, 10.0)
    assert result.unit == "ratio"
    assert result.value == pytest.approx(0.9)


def test_asr_confidence_mean_times_coverage():
    words = [Word("a", 0.0, 1.0, 0.8), Word("b", 1.0, 2.0, 1.0)]
    # mean prob 0.9, coverage 2/4 = 0.5 → 0.45
    assert asr_confidence(words, transcribed_duration_s=2.0, expected_speech_duration_s=4.0) == pytest.approx(0.45)


def test_prosody_confidence_snr_anchors():
    assert snr_factor(10.0) == pytest.approx(0.3)
    assert snr_factor(20.0) == pytest.approx(1.0)
    assert snr_factor(15.0) == pytest.approx(0.65)
    # voiced 1.0, snr 10 dB, no octave error → 0.3
    assert prosody_confidence(voiced_ratio=1.0, snr_db=10.0, octave_error_ratio=0.0) == pytest.approx(0.3)
    assert prosody_confidence(voiced_ratio=1.0, snr_db=20.0, octave_error_ratio=0.0) == pytest.approx(1.0)
    assert prosody_confidence(voiced_ratio=1.0, snr_db=20.0, octave_error_ratio=0.2) == pytest.approx(0.8)


def test_persist_metrics_writes_file(tmp_path):
    from metrics.compute import persist_session_metrics

    transcript = {
        "language": "en",
        "duration": 60.0,
        "mean_word_probability": 0.9,
        "segments": [
            {
                "start": 0.0,
                "end": 60.0,
                "text": "hello world " * 20,
                "words": [
                    {"word": "hello", "start": i * 2.0, "end": i * 2.0 + 0.4, "probability": 0.9}
                    for i in range(30)
                ],
            }
        ],
    }
    audio = {
        "duration_s": 60.0,
        "voiced_ratio": 0.8,
        "snr_db": 22.0,
        "octave_jump_ratio": 0.0,
        "syllable_count": 40,
        "phonation_time_s": 20.0,
        "pvq_median": 0.16,
        "pitch_range_st_median": 6.0,
        "monotone_windows_ratio": 0.0,
        "intensity_sd_db_median": 3.0,
        "emphasis_rate_per_min": 8.0,
        "music_flag": False,
        "confidence": {},
    }
    t_path = tmp_path / "transcript.json"
    a_path = tmp_path / "audio_metrics.json"
    t_path.write_text(json.dumps(transcript))
    a_path.write_text(json.dumps(audio))
    packages = Path(__file__).resolve().parents[3] / "packages"
    dest = persist_session_metrics(
        output_dir=tmp_path,
        transcript_path=t_path,
        audio_metrics_path=a_path,
        packages_dir=packages,
        slot_s=90.0,
    )
    payload = json.loads(dest.read_text())
    assert dest.name == "metrics.json"
    assert payload["scoring_config_version"] == "1.0.0"
    assert "pp_wpm" in payload["metrics"]
    assert payload["metrics"]["pp_wpm"]["unit"] == "words_per_minute"
    assert payload["metrics"]["tm_pct_of_slot"]["unit"] == "ratio"
    assert payload["filler_benchmark"]["source"] == "S12"
