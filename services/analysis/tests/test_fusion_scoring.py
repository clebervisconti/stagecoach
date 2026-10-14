"""Fusion + report tests for issue #30."""

import json
import sys
from pathlib import Path

import jsonschema
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.stages.fusion_scoring import (
    VIDEO_CATEGORIES,
    _ensure_scoring_path,
    _packages_dir,
    _walk_packages,
    run_fusion_scoring,
)
from pipeline.stages.report import FORBIDDEN, build_report, run_report_stage

FIXTURES = Path(__file__).parent / "fixtures"
PACKAGES = Path(__file__).parents[3] / "packages"
SCHEMA = json.loads((PACKAGES / "schemas" / "analysis_result.v1.json").read_text())

SCORED_AUDIO_TEXT = {
    "core_message",
    "structure",
    "storytelling",
    "audience_adaptation",
    "opening_close",
    "clarity",
    "impact",
    "pace_pausing",
    "vocal_variety",
    "fluency",
}


def _metrics_payload() -> dict:
    def m(metric_id: str, value: float, unit: str, confidence: float = 0.85) -> dict:
        return {
            "id": metric_id,
            "value": value,
            "unit": unit,
            "basis": "heuristic",
            "source": "H",
            "confidence": confidence,
            "applicable": True,
        }

    return {
        "version": "1.0.0",
        "scoring_config_version": "1.0.0",
        "asr_confidence": 0.85,
        "prosody_confidence": 0.8,
        "metrics": {
            "pp_wpm": m("pp_wpm", 145.0, "words_per_minute"),
            "pp_pace_cv": m("pp_pace_cv", 0.12, "coefficient_of_variation"),
            "pp_rush_index": m("pp_rush_index", 1.02, "ratio"),
            "pp_boundary_pause_ratio": m("pp_boundary_pause_ratio", 0.6, "ratio"),
            "pp_unplanned_long_pauses_per_10min": m(
                "pp_unplanned_long_pauses_per_10min", 0.5, "per_10min"
            ),
            "pp_mean_length_of_run": m("pp_mean_length_of_run", 9.0, "words"),
            "vv_pvq_median": m("vv_pvq_median", 0.18, "ratio"),
            "vv_pitch_range_st": m("vv_pitch_range_st", 8.0, "semitones"),
            "vv_monotone_windows_ratio": m("vv_monotone_windows_ratio", 0.08, "ratio"),
            "vv_intensity_variation_db": m("vv_intensity_variation_db", 4.0, "decibels"),
            "vv_emphasis_rate_per_min": m("vv_emphasis_rate_per_min", 10.0, "per_minute"),
            "fl_filler_sounds_per_min": m("fl_filler_sounds_per_min", 2.0, "per_minute"),
            "fl_filler_words_per_min": m("fl_filler_words_per_min", 1.0, "per_minute"),
            "fl_hedges_apologies_per_10min": m("fl_hedges_apologies_per_10min", 1.0, "per_10min"),
            "fl_repetitions_restarts_per_min": m(
                "fl_repetitions_restarts_per_min", 0.2, "per_minute"
            ),
            "tm_pct_of_slot": m("tm_pct_of_slot", 0.9, "ratio", 1.0),
        },
    }


def _write_inputs(tmp_path: Path, *, with_content: bool, short: bool = False) -> dict:
    if short:
        transcript = {
            "language": "en",
            "duration": 8.0,
            "mean_word_probability": 0.9,
            "model": "faster-whisper-tiny",
            "segments": [
                {
                    "id": 0,
                    "start": 0.0,
                    "end": 8.0,
                    "text": "Um hello there.",
                    "words": [
                        {"word": "Um", "start": 0.0, "end": 0.3, "probability": 0.9},
                        {"word": "hello", "start": 0.4, "end": 0.8, "probability": 0.95},
                    ],
                }
            ],
        }
    else:
        transcript = json.loads((FIXTURES / "synthetic_transcript.json").read_text())
        transcript["model"] = "faster-whisper-tiny"
        transcript["mean_word_probability"] = transcript.get("mean_word_prob", 0.92)
        # Storytelling and impact require 400 speech words (scoring.yaml min_evidence).
        extra = [
            "Let me walk through one more concrete example so the takeaway is unmistakable.",
            "A second customer, Miguel, ran the same workflow every Monday morning for his regional team.",
            "He used to open twelve screens, copy numbers by hand, and hope the report still matched the source.",
            "After we removed the extra steps, he finished the same report before the standup started.",
            "That is the same pattern: name the core job, cut the friction, and measure what remains.",
            "If you keep only the work that serves the core message, the close writes itself.",
        ]
        t = float(transcript["duration"])
        next_id = len(transcript["segments"])
        for i, text in enumerate(extra):
            start = t + i * 8.0
            end = start + 8.0
            transcript["segments"].append(
                {"id": next_id + i, "start": start, "end": end, "text": text}
            )
        transcript["duration"] = t + 8.0 * len(extra)
    (tmp_path / "transcript.json").write_text(json.dumps(transcript))
    (tmp_path / "metrics.json").write_text(json.dumps(_metrics_payload()))
    (tmp_path / "audio_metrics.json").write_text(
        json.dumps(
            {
                "duration_s": transcript["duration"],
                "voiced_s": 90.0 if not short else 3.0,
                "voiced_ratio": 0.7,
                "snr_db": 22.0,
                "music_flag": False,
                "noise_flag": False,
                "pvq_windows": [{"start": 0, "value": 0.18}],
            }
        )
    )
    if with_content:
        (tmp_path / "content.json").write_text((FIXTURES / "synthetic_content.json").read_text())
    return {"transcript": transcript}


def test_packages_lookup_does_not_assume_repo_depth():
    """Worker image path is /app/pipeline/stages/... — parents[4] must not be required."""
    _ensure_scoring_path()
    packages = _packages_dir()
    assert (packages / "scoring-config" / "v1.0.0" / "scoring.yaml").exists()
    assert any((p / "schemas" / "analysis_result.v1.json").exists() for p in _walk_packages())


def test_missing_content_marks_text_categories_unavailable(tmp_path: Path):
    _write_inputs(tmp_path, with_content=False, short=True)
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000001",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        camera_setup="audio_only",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    for cid in (
        "core_message",
        "structure",
        "storytelling",
        "audience_adaptation",
        "opening_close",
        "clarity",
        "impact",
    ):
        assert by_id[cid]["applicable"] is False
        assert by_id[cid]["score"] is None
        assert "not run" in (by_id[cid]["na_reason"] or "").lower() or "words" in (
            by_id[cid]["na_reason"] or ""
        ).lower()
    for cid, reason in VIDEO_CATEGORIES.items():
        assert by_id[cid]["applicable"] is False
        assert by_id[cid]["score"] is None
        assert by_id[cid]["na_reason"] == reason
    assert result["provenance"]["scoring_config_version"] == "1.0.0"
    jsonschema.validate(instance=result, schema=SCHEMA)


def test_content_and_metrics_score_audio_text_categories(tmp_path: Path):
    _write_inputs(tmp_path, with_content=True)
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000002",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        slot_min=4,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
        content_path=tmp_path / "content.json",
    )
    jsonschema.validate(instance=result, schema=SCHEMA)
    by_id = {c["id"]: c for c in result["categories"]}
    for cid in SCORED_AUDIO_TEXT:
        assert by_id[cid]["applicable"] is True, cid
        assert by_id[cid]["score"] is not None, cid
    for cid in VIDEO_CATEGORIES:
        assert by_id[cid]["applicable"] is False
        assert by_id[cid]["score"] is None
    assert by_id["time_management"]["applicable"] is True
    assert by_id["time_management"]["score"] is not None
    assert by_id["qa"]["applicable"] is False
    metric_ids = {m["id"] for m in result["metrics"]}
    assert "pp_wpm" in metric_ids
    assert "cm_message_identifiable" in metric_ids
    assert "gb_gesture_activity_ratio" not in metric_ids
    assert result["provenance"]["scoring_config_version"] == "1.0.0"
    assert any(m["name"] == "faster-whisper-tiny" for m in result["provenance"]["models"])
    assert (tmp_path / "analysis_result.json").exists()
    assert (tmp_path / "series_pace.json").exists()


def test_report_phrases_only_fact_numbers_and_attaches_drills(tmp_path: Path):
    _write_inputs(tmp_path, with_content=True)
    analysis = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000003",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        slot_min=4,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
        content_path=tmp_path / "content.json",
    )
    report = run_report_stage(output_dir=tmp_path, analysis=analysis, packages_dir=PACKAGES)
    jsonschema.validate(instance=report, schema=SCHEMA)
    text = json.dumps(report["insights"])
    assert FORBIDDEN.search(text) is None
    assert report["insights"]["summary"]
    assert (tmp_path / "report.json").exists()
    # Re-run number check by rebuilding; any invented number would raise.
    build_report(
        analysis=json.loads((tmp_path / "analysis_result.json").read_text()),
        output_path=tmp_path / "report2.json",
        packages_dir=PACKAGES,
    )


def test_never_invents_video_or_missing_llm_metrics(tmp_path: Path):
    _write_inputs(tmp_path, with_content=False, short=True)
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000004",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    invented = {
        "va_words_per_slide_median",
        "gb_gesture_activity_ratio",
        "ec_audience_facing_ratio",
        "fa_smile_presence_ratio",
        "st_logical_flow",
        "sto_story_quality",
        "aud_relevance_framing",
        "fl_grammar_llm",
    }
    present = {m["id"] for m in result["metrics"]}
    assert invented.isdisjoint(present)


def test_consent_denied_sets_video_na_reasons(tmp_path: Path):
    _write_inputs(tmp_path, with_content=False, short=True)
    (tmp_path / "consents.json").write_text(
        json.dumps(
            {
                "policy_id": "1.0.0",
                "purposes": {
                    "video_analysis": {"granted": False},
                    "expression_analysis": {"granted": False},
                    "keep_detailed_tracking": {"granted": False},
                },
            }
        )
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000037",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["gestures_body"]["applicable"] is False
    assert "consent is off" in (by_id["gestures_body"]["na_reason"] or "")
    assert by_id["facial_affect"]["applicable"] is False
    assert "Expression analysis is off" in (by_id["facial_affect"]["na_reason"] or "")
    assert "gb_gesture_activity_ratio" not in {m["id"] for m in result["metrics"]}
