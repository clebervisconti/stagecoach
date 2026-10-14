"""Category 15 energy & presence fusion (issue #45). No SER, no confidence detection."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.energy import (
    UNITS,
    composite_energy,
    compute_energy_metrics,
    energy_trajectory,
    key_moment_lift,
    too_soft_ratio,
)
from pipeline.stages.fusion_scoring import run_fusion_scoring

PACKAGES = Path(__file__).parents[3] / "packages"


def _config() -> dict:
    return yaml.safe_load(
        (PACKAGES / "scoring-config" / "v1.0.0" / "scoring.yaml").read_text()
    )


def test_units_match_scoring_yaml() -> None:
    for metric_id, spec in _config()["categories"]["energy_presence"][
        "metrics"
    ].items():
        assert UNITS[metric_id] == spec["unit"]


def test_too_soft_uses_median_minus_12db() -> None:
    ratio = too_soft_ratio([0.0, 1.0, 2.0, -13.0, -20.0])
    assert ratio is not None
    assert ratio == 0.4


def test_audio_only_composite_omits_missing_modalities() -> None:
    duration = 360.0
    pvq = [{"start": t, "value": 0.1 + 0.01 * (t / 60.0)} for t in range(0, 360, 10)]
    loud = [{"start": t, "value": -2.0 + 0.5 * (t / 60.0)} for t in range(0, 360, 10)]
    audio_only = composite_energy({"loudness": loud, "pvq": pvq}, duration)
    with_gesture = composite_energy(
        {
            "loudness": loud,
            "pvq": pvq,
            "gesture": [{"start": t, "value": 0.1} for t in range(0, 360, 1)],
        },
        duration,
    )
    assert audio_only
    assert with_gesture
    assert all(p["n_modalities"] == 2 for p in audio_only)
    assert all(p["n_modalities"] == 3 for p in with_gesture)


def test_trajectory_last_third_minus_first() -> None:
    series = [
        {"t": 0.0, "value": 0.0},
        {"t": 60.0, "value": 0.0},
        {"t": 120.0, "value": 1.0},
        {"t": 180.0, "value": 1.0},
        {"t": 240.0, "value": 2.0},
        {"t": 300.0, "value": 2.0},
    ]
    delta = energy_trajectory(series, 360.0)
    assert delta == 2.0


def test_sparse_series_does_not_invent_trajectory() -> None:
    assert energy_trajectory([{"t": 0.0, "value": 0.5}], 180.0) is None


def test_key_moment_lift_and_missing_keys() -> None:
    series = [
        {"t": 0.0, "value": 2.0},
        {"t": 60.0, "value": 0.0},
        {"t": 120.0, "value": 0.0},
    ]
    assert key_moment_lift(series, [0.0]) == 2.0
    assert key_moment_lift(series, []) is None


def test_recovery_na_without_disruptions_and_without_llm() -> None:
    none = compute_energy_metrics(
        audio={
            "duration_s": 360,
            "too_soft_ratio": 0.1,
            "pvq_windows": [{"start": t, "value": 0.2} for t in range(0, 360, 10)],
        },
        duration_s=360,
    )
    assert none is not None
    assert none["metrics"]["ep_recovery"]["applicable"] is False
    assert none["metrics"]["ep_recovery"]["failure_mode"] == "no_disruptions"

    pauses = {"pauses": [{"kind": "long", "duration": 4.0, "start": 10.0, "end": 14.0}]}
    missing_llm = compute_energy_metrics(
        audio={"duration_s": 360, "too_soft_ratio": 0.1},
        pauses=pauses,
        duration_s=360,
    )
    assert missing_llm is not None
    assert missing_llm["metrics"]["ep_recovery"]["applicable"] is False
    assert missing_llm["metrics"]["ep_recovery"]["failure_mode"] == "llm_unavailable"
    assert missing_llm["metrics"]["ep_recovery"]["value"] is None


def test_expressivity_ignored_without_opt_in() -> None:
    windows = [{"start": t, "value": 0.4} for t in range(0, 360, 5)]
    off = compute_energy_metrics(
        audio={
            "duration_s": 360,
            "pvq_windows": [{"start": t, "value": 0.2} for t in range(0, 360, 10)],
        },
        expression={"expressivity_windows": windows},
        duration_s=360,
        expression_opt_in=False,
    )
    on = compute_energy_metrics(
        audio={
            "duration_s": 360,
            "pvq_windows": [{"start": t, "value": 0.2} for t in range(0, 360, 10)],
        },
        expression={"expressivity_windows": windows},
        duration_s=360,
        expression_opt_in=True,
    )
    assert off is not None and "expressivity" not in off["modalities_used"]
    assert on is not None and "expressivity" in on["modalities_used"]


def test_no_ser_or_confidence_detection_in_source() -> None:
    root = Path(__file__).resolve().parents[1]
    energy = (root / "pipeline" / "energy.py").read_text()
    fusion = (root / "pipeline" / "stages" / "fusion_scoring.py").read_text()
    assert "Not confidence detection" in energy
    assert "confidence detection" not in fusion.lower()
    assert "No SER" in energy
    for term in ("happy", "sad", "angry", "anxious"):
        assert term not in energy.lower()


def test_fusion_scores_energy_when_series_exist(tmp_path: Path) -> None:
    duration = 360.0
    transcript = {
        "language": "en",
        "duration": duration,
        "mean_word_probability": 0.9,
        "model": "faster-whisper-tiny",
        "segments": [
            {
                "id": i,
                "start": i * 15.0,
                "end": i * 15.0 + 14.0,
                "text": "The key point is we shipped the change for the team this week.",
            }
            for i in range(24)
        ],
    }
    (tmp_path / "transcript.json").write_text(json.dumps(transcript))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(
        json.dumps(
            {
                "duration_s": duration,
                "voiced_s": 300.0,
                "too_soft_ratio": 0.08,
                "pvq_windows": [
                    {"start": t, "value": 0.12 + 0.02 * (t / 60.0)}
                    for t in range(0, 360, 10)
                ],
                "intensity_windows": [
                    {"start": t, "value": -1.0 + 0.4 * (t / 60.0)}
                    for t in range(0, 360, 10)
                ],
            }
        )
    )
    (tmp_path / "gesture_metrics.json").write_text(
        json.dumps(
            {
                "person_visible_ratio": 0.9,
                "activity_windows": [
                    {"start": t, "value": 0.2 + 0.1 * (t / 60.0)}
                    for t in range(0, 360, 1)
                ],
            }
        )
    )
    (tmp_path / "content.json").write_text(
        json.dumps(
            {
                "message": {
                    "core_message": {"seg_ids": ["S0020"], "level": 4},
                    "cta": {"seg_ids": ["S0023"], "specificity_level": 4},
                },
                "energy": {
                    "confident_language_level": 4.0,
                    "recovery_level": 3.5,
                    "disruptions": True,
                    "disruption_count": 1,
                },
            }
        )
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000045",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        packages_dir=PACKAGES,
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["energy_presence"]["applicable"] is True
    assert by_id["energy_presence"]["score"] is not None
    present = {m["id"] for m in result["metrics"]}
    assert "ep_too_soft_ratio" in present
    assert "ep_energy_trajectory" in present
    assert "ep_confident_language" in present
    assert "ep_recovery" in present
    blob = json.dumps(result)
    assert "confidence detection" not in blob.lower()
    assert "emotion" not in blob.lower() or "emotion_inference" in blob


def test_fusion_na_when_no_energy_inputs(tmp_path: Path) -> None:
    (tmp_path / "transcript.json").write_text(
        json.dumps(
            {
                "language": "en",
                "duration": 180.0,
                "mean_word_probability": 0.9,
                "segments": [
                    {
                        "id": 0,
                        "start": 0,
                        "end": 180,
                        "text": "hello " * 80,
                        "words": [],
                    }
                ],
            }
        )
    )
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(
        json.dumps({"duration_s": 180.0, "voiced_s": 90.0})
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000046",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        packages_dir=PACKAGES,
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["energy_presence"]["applicable"] is False
    assert by_id["energy_presence"]["score"] is None
    assert (
        "N/A" in (by_id["energy_presence"]["na_reason"] or "")
        or "missing" in (by_id["energy_presence"]["na_reason"] or "").lower()
        or "needs" in (by_id["energy_presence"]["na_reason"] or "").lower()
    )
