"""E3-5: screen_flow and online_engagement use scoring-config v1.1.0."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.stages.fusion_scoring import run_fusion_scoring

PACKAGES = Path(__file__).resolve().parents[4] / "packages"


def _transcript(duration: float, *, words: int) -> dict:
    text = " ".join(f"word{i}" for i in range(words))
    return {
        "language": "en",
        "duration": duration,
        "mean_word_probability": 0.92,
        "model": "faster-whisper-tiny",
        "segments": [
            {
                "id": "S0001",
                "start": 0.0,
                "end": duration,
                "text": text,
            }
        ],
    }


def _write_common(tmp_path: Path, transcript: dict) -> None:
    (tmp_path / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}, "asr_confidence": 0.92}), encoding="utf-8")
    (tmp_path / "audio_metrics.json").write_text(
        json.dumps({"duration_s": transcript["duration"], "voiced_s": transcript["duration"]}),
        encoding="utf-8",
    )


def _screen_flow(*, visible_s: float, segments: int, metrics: list[dict]) -> dict:
    rows = []
    span = visible_s / max(segments, 1)
    for index in range(segments):
        rows.append({"t_start": index * span, "t_end": (index + 1) * span, "type": "SLIDE"})
    return {
        "version": "1.0.0",
        "screen_visible_s": visible_s,
        "segments": rows,
        "metrics": metrics,
        "content_judgment": False,
    }


def _run(tmp_path: Path, transcript: dict, *, mode: str) -> dict:
    return run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000173",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
        delivery_mode=mode,
    )


def test_screen_flow_score_follows_the_v110_curve(tmp_path: Path):
    transcript = _transcript(180, words=40)
    _write_common(tmp_path, transcript)
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=180,
                segments=2,
                metrics=[
                    {
                        "id": "sf_clean_transition_ratio",
                        "value": 0.6,
                        "unit": "ratio",
                        "applicable": True,
                        "confidence": 0.9,
                        "source": "H",
                    }
                ],
            )
        ),
        encoding="utf-8",
    )
    result = _run(tmp_path, transcript, mode="webinar")
    by_id = {row["id"]: row for row in result["categories"]}
    assert by_id["screen_flow"]["applicable"] is True
    assert by_id["screen_flow"]["score"] == 67
    metric = next(row for row in result["metrics"] if row["id"] == "sf_clean_transition_ratio")
    assert metric["score"] == pytest.approx(40 + (0.2 / 0.3) * 40)


def test_min_evidence_blocks_a_short_screen(tmp_path: Path):
    transcript = _transcript(30, words=20)
    _write_common(tmp_path, transcript)
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=30,
                segments=1,
                metrics=[
                    {
                        "id": "sf_clean_transition_ratio",
                        "value": 0.9,
                        "unit": "ratio",
                        "applicable": True,
                        "confidence": 0.9,
                    }
                ],
            )
        ),
        encoding="utf-8",
    )
    result = _run(tmp_path, transcript, mode="online_talk")
    by_id = {row["id"]: row for row in result["categories"]}
    assert by_id["screen_flow"]["applicable"] is False
    assert by_id["screen_flow"]["na_code"] == "no_screen"
    assert "2 minutes" in (by_id["screen_flow"]["na_reason"] or "")


def test_stage_ignores_a_screen_flow_file(tmp_path: Path):
    transcript = _transcript(180, words=40)
    _write_common(tmp_path, transcript)
    bare = _run(tmp_path, transcript, mode="stage")
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=180,
                segments=2,
                metrics=[
                    {
                        "id": "sf_clean_transition_ratio",
                        "value": 0.6,
                        "unit": "ratio",
                        "applicable": True,
                        "confidence": 0.9,
                    },
                    {
                        "id": "oe_direct_address_per_100w",
                        "value": 3,
                        "unit": "per_100_words",
                        "applicable": True,
                        "confidence": 0.9,
                    },
                ],
            )
        ),
        encoding="utf-8",
    )
    with_file = _run(tmp_path, transcript, mode="stage")
    bare_by = {row["id"]: row for row in bare["categories"]}
    file_by = {row["id"]: row for row in with_file["categories"]}
    assert file_by["screen_flow"]["applicable"] is False
    assert file_by["screen_flow"]["na_code"] == "stage_mode"
    assert file_by["online_engagement"]["na_code"] == "stage_mode"
    for cat_id, row in bare_by.items():
        assert file_by[cat_id]["score"] == row["score"]
        assert file_by[cat_id]["applicable"] == row["applicable"]
        assert file_by[cat_id]["weight_used"] == row["weight_used"]


def test_no_screen_still_scores_engagement_from_speech(tmp_path: Path):
    transcript = _transcript(180, words=80)
    _write_common(tmp_path, transcript)
    result = _run(tmp_path, transcript, mode="webinar")
    by_id = {row["id"]: row for row in result["categories"]}
    assert by_id["screen_flow"]["applicable"] is False
    assert by_id["screen_flow"]["na_code"] == "no_screen"
    assert by_id["online_engagement"]["applicable"] is True
    assert by_id["online_engagement"]["score"] is not None
    assert not (tmp_path / "screen_flow.json").exists()


def test_video_consent_off_still_scores_screen_flow(tmp_path: Path):
    transcript = _transcript(180, words=40)
    _write_common(tmp_path, transcript)
    (tmp_path / "consents.json").write_text(
        json.dumps(
            {
                "policy_id": "1.0.0",
                "purposes": {
                    "video_analysis": {"granted": False},
                    "expression_analysis": {"granted": False},
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=180,
                segments=2,
                metrics=[
                    {
                        "id": "sf_signpost_ratio",
                        "value": 0.5,
                        "unit": "ratio",
                        "applicable": True,
                        "confidence": 0.85,
                    }
                ],
            )
        ),
        encoding="utf-8",
    )
    result = _run(tmp_path, transcript, mode="recorded_video")
    by_id = {row["id"]: row for row in result["categories"]}
    assert by_id["screen_flow"]["applicable"] is True
    assert by_id["on_camera_presence"]["applicable"] is False
    assert by_id["on_camera_presence"]["na_code"] == "consent_video_off"


def test_audio_only_skips_screen_flow_and_keeps_engagement(tmp_path: Path):
    transcript = _transcript(180, words=40)
    _write_common(tmp_path, transcript)
    (tmp_path / "analysis_flags.json").write_text(json.dumps({"audio_only_chosen": True}), encoding="utf-8")
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=180,
                segments=2,
                metrics=[
                    {
                        "id": "sf_signpost_ratio",
                        "value": 0.5,
                        "unit": "ratio",
                        "applicable": True,
                        "confidence": 0.85,
                    }
                ],
            )
        ),
        encoding="utf-8",
    )
    result = _run(tmp_path, transcript, mode="webinar")
    by_id = {row["id"]: row for row in result["categories"]}
    assert by_id["screen_flow"]["na_code"] == "audio_only_chosen"
    assert by_id["online_engagement"]["applicable"] is True


def test_report_opportunities_include_scored_flow_categories(tmp_path: Path):
    from pipeline.stages.report import run_report_stage

    transcript = _transcript(180, words=40)
    _write_common(tmp_path, transcript)
    (tmp_path / "screen_flow.json").write_text(
        json.dumps(
            _screen_flow(
                visible_s=180,
                segments=2,
                metrics=[
                    {
                        "id": "sf_dead_air_per_10min",
                        "value": 6,
                        "unit": "per_10_min",
                        "applicable": True,
                        "confidence": 0.9,
                    },
                    {
                        "id": "oe_open_speech_start_s",
                        "value": 30,
                        "unit": "seconds",
                        "applicable": True,
                        "confidence": 0.9,
                    },
                ],
            )
        ),
        encoding="utf-8",
    )
    _run(tmp_path, transcript, mode="webinar")
    report = run_report_stage(output_dir=tmp_path, packages_dir=PACKAGES)
    ids = {row["category_id"] for row in report["insights"]["opportunities"]}
    assert "screen_flow" in ids or "online_engagement" in ids
