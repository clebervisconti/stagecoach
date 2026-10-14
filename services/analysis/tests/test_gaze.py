"""Category 13 audience-facing / gaze proxies (issue #41) on synthetic head pose."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parents[3] / "packages" / "scoring"))

from pipeline.accessibility import persist_accessibility
from pipeline.consent import VisionDecision
from pipeline.stages.fusion_scoring import run_fusion_scoring
from pipeline.stages.vision import run_vision_stage
from pipeline.vision.gaze import UNITS, compute_gaze_metrics, eye_gaze_deg
from pipeline.vision.synthetic import scripted_events

TEST_KEY = bytes.fromhex("11" * 32)
PACKAGES = Path(__file__).parents[3] / "packages"
SCORING_YAML = PACKAGES / "scoring-config" / "v1.0.0" / "scoring.yaml"
VIDEO = VisionDecision(
    run_pose=True,
    run_hands=True,
    run_face_landmarks=True,
    run_expression_metrics=False,
    keep_raw_landmarks=False,
    skip_reason=None,
)
CONSENT_ON = {
    "policy_id": "1.0.0",
    "purposes": {
        "video_analysis": {"granted": True},
        "expression_analysis": {"granted": False},
        "keep_detailed_tracking": {"granted": False},
    },
}


def _face(t: float, yaw: float, pitch: float, *, px: float = 90.0, visible: bool = True, gaze=(0.0, 0.0)) -> dict:
    gx, gy = gaze
    return {
        "t": t,
        "face_visible": 1.0 if visible else 0.0,
        "face_height_px": px,
        "yaw_deg": yaw,
        "pitch_deg": pitch,
        "blendshapes": {
            "eyeLookInLeft": max(0.0, -gx / 30.0),
            "eyeLookOutLeft": max(0.0, gx / 30.0),
            "eyeLookInRight": max(0.0, gx / 30.0),
            "eyeLookOutRight": max(0.0, -gx / 30.0),
            "eyeLookUpLeft": max(0.0, -gy / 30.0),
            "eyeLookUpRight": max(0.0, -gy / 30.0),
            "eyeLookDownLeft": max(0.0, gy / 30.0),
            "eyeLookDownRight": max(0.0, gy / 30.0),
        },
    }


def test_units_match_scoring_yaml():
    config = yaml.safe_load(SCORING_YAML.read_text())
    for metric_id, spec in config["categories"]["eye_contact"]["metrics"].items():
        assert metric_id in UNITS
        assert spec["unit"] == UNITS[metric_id]


def test_to_camera_facing_uses_tight_head_and_gaze():
    rows = [_face(i / 10.0, 0.0, 0.0) for i in range(50)]
    payload = compute_gaze_metrics(rows, duration_s=5.0, setup="to_camera")
    assert payload is not None
    assert payload["eye_contact"] is False
    assert payload["l2cs_net"] is False
    assert payload["proxy_label"] == "audience-facing time (head orientation)"
    assert payload["metrics"]["ec_audience_facing_ratio"]["value"] == pytest.approx(1.0)
    assert payload["metrics"]["ec_gaze_distribution_evenness"]["applicable"] is False
    turned = [_face(i / 10.0, 40.0, 0.0) for i in range(50)]
    away = compute_gaze_metrics(turned, duration_s=5.0, setup="to_camera")
    assert away["metrics"]["ec_audience_facing_ratio"]["value"] == pytest.approx(0.0)


def test_stage_allows_wider_yaw_and_scores_evenness():
    rows = []
    for i in range(80):
        t = i / 10.0
        yaw = -20.0 if i < 40 else 20.0
        rows.append(_face(t, yaw, 0.0, px=50.0))
    payload = compute_gaze_metrics(rows, duration_s=8.0, setup="stage")
    assert payload is not None
    assert payload["use_eye_gaze"] is False
    assert payload["metrics"]["ec_audience_facing_ratio"]["value"] > 0.8
    assert payload["metrics"]["ec_gaze_distribution_evenness"]["applicable"] is True
    assert payload["metrics"]["ec_gaze_distribution_evenness"]["value"] > 0.3
    assert payload["metrics"]["ec_audience_facing_ratio"]["confidence"] <= 0.6


def test_reading_head_down_ratio():
    rows = [_face(i / 10.0, 0.0, -28.0) for i in range(40)] + [_face(4 + i / 10.0, 0.0, 0.0) for i in range(40)]
    payload = compute_gaze_metrics(rows, duration_s=8.0, setup="to_camera")
    assert payload["metrics"]["ec_reading_head_down_ratio"]["value"] == pytest.approx(0.5, abs=0.05)


def test_holds_count_long_facing_episodes():
    rows = [_face(i / 10.0, 0.0, 0.0) for i in range(50)]
    payload = compute_gaze_metrics(rows, duration_s=5.0, setup="to_camera")
    assert payload["metrics"]["ec_gaze_holds_per_min"]["value"] > 0


def test_wide_shot_disables_eye_gaze_and_caps_confidence():
    rows = [_face(i / 10.0, 0.0, 0.0, px=40.0) for i in range(40)]
    payload = compute_gaze_metrics(rows, duration_s=4.0, setup="to_camera")
    assert payload["wide_shot"] is True
    assert payload["use_eye_gaze"] is False
    assert payload["metrics"]["ec_audience_facing_ratio"]["confidence"] <= 0.6


def test_audio_only_and_opt_out():
    rows = [_face(0.1, 0.0, 0.0)]
    assert compute_gaze_metrics(rows, duration_s=1.0, audio_only=True) is None
    assert compute_gaze_metrics(
        rows, duration_s=1.0, accessibility={"prefers_no_video_metrics": True}
    ) is None
    assert compute_gaze_metrics(rows, duration_s=1.0, setup="screen_recording") is None


def test_no_l2cs_and_blendshape_gaze_is_heuristic():
    gx, gy = eye_gaze_deg({"eyeLookOutLeft": 0.5, "eyeLookInLeft": 0.0})
    assert gx is not None
    src = (Path(__file__).parent.parent / "pipeline" / "vision" / "gaze.py").read_text()
    assert "l2cs" in src.lower()
    assert "not used" in src.lower() or "not re-checked" in src.lower()
    req = (Path(__file__).parent.parent / "requirements.txt").read_text().lower()
    assert "l2cs" not in req


def test_vision_writes_gaze_metrics(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    payload = json.loads((tmp_path / "gaze_metrics.json").read_text())
    assert payload["eye_contact"] is False
    assert payload["l2cs_net"] is False
    for metric_id in UNITS:
        assert metric_id in payload["metrics"]


def test_fusion_scores_eye_contact(tmp_path: Path):
    persist_accessibility(tmp_path, {})
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "transcript.json").write_text(
        json.dumps({"language": "en", "duration": 5.0, "segments": [{"id": "S0001", "start": 0, "end": 5, "text": "Hi"}]})
    )
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 5}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000141",
        output_dir=tmp_path,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["eye_contact"]["applicable"] is True
    assert by_id["eye_contact"]["score"] is not None
    assert "ec_audience_facing_ratio" in {m["id"] for m in result["metrics"]}
    blob = json.dumps(result).lower()
    assert "audience-facing" in blob or "head orientation" in blob
    for item in result["evidence"]:
        text = (item.get("text") or "").lower()
        if "eye contact" in text:
            assert "not eye contact" in text or "proxy" in text or "head orientation" in text
    assert result["quality"].get("face_visible_ratio") is not None


def test_fusion_na_when_consent_on_but_no_gaze_file(tmp_path: Path):
    persist_accessibility(tmp_path, {})
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "transcript.json").write_text(
        json.dumps({"language": "en", "duration": 5.0, "segments": [{"id": "S0001", "start": 0, "end": 5, "text": "Hi"}]})
    )
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 5}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000142",
        output_dir=tmp_path,
        camera_setup="to_camera",
        packages_dir=PACKAGES,
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["eye_contact"]["applicable"] is False
    assert by_id["eye_contact"]["score"] is None
    assert "visible face" in (by_id["eye_contact"]["na_reason"] or "").lower()
    assert "ec_audience_facing_ratio" not in {m["id"] for m in result["metrics"]}
