"""Category 12 gestures & body (issue #40) on synthetic trajectories."""

from __future__ import annotations

import json
import math
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
from pipeline.vision.gestures import (
    UNITS,
    compute_gesture_metrics,
    gb_gesture_activity_ratio,
    gb_gesture_speech_sync,
    gb_purposeful_movement,
    gb_sway_index,
)
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


def _row(
    t: float,
    *,
    speed: float = 0.0,
    wrist_y: float = -0.6,
    wrist_x: float = 0.4,
    vis: float = 1.0,
    hip_x: float = 0.5,
    hip_visible: float = 1.0,
    crossed: float = 0.0,
    person: float = 1.0,
    elbow_vis: float = 1.0,
    sw: float = 0.2,
) -> dict:
    return {
        "t": t,
        "person_visible": person,
        "wrist_speed_l": speed,
        "wrist_speed_r": speed,
        "wrist_l_x": -wrist_x,
        "wrist_r_x": wrist_x,
        "wrist_l_y": wrist_y,
        "wrist_r_y": wrist_y,
        "wrist_l_vis": vis,
        "wrist_r_vis": vis,
        "elbow_l_vis": elbow_vis,
        "elbow_r_vis": elbow_vis,
        "hip_mid_x": hip_x,
        "hip_mid_y": 0.6,
        "hip_visible": hip_visible,
        "shoulder_width": sw,
        "crossed_arms": crossed,
        "hand_face_dist": 1.2,
    }


def _still(seconds: float = 8.0, fps: float = 15.0) -> list[dict]:
    n = int(round(seconds * fps))
    return [_row(i / fps) for i in range(n)]


def _active(seconds: float = 8.0, fps: float = 15.0) -> list[dict]:
    rows = []
    n = int(round(seconds * fps))
    for i in range(n):
        t = i / fps
        # Alternate 1-s windows: moving vs still → activity ratio ~0.5.
        speed = 0.9 if int(t) % 2 == 0 else 0.05
        rows.append(_row(t, speed=speed, wrist_y=-0.7, wrist_x=0.45))
    return rows


def test_units_match_scoring_yaml():
    config = yaml.safe_load(SCORING_YAML.read_text())
    for metric_id, spec in config["categories"]["gestures_body"]["metrics"].items():
        assert metric_id in UNITS
        assert spec["unit"] == UNITS[metric_id]


def test_activity_ratio_on_alternating_windows():
    rows = _active()
    value = gb_gesture_activity_ratio(rows)
    assert value == pytest.approx(0.5, abs=0.15)


def test_frozen_trajectory_is_low_activity():
    rows = _still()
    value = gb_gesture_activity_ratio(rows)
    assert value is not None
    assert value < 0.1


def test_hands_gate_marks_hand_metrics_na():
    rows = [_row(i / 15.0, vis=0.1, elbow_vis=1.0) for i in range(60)]
    payload = compute_gesture_metrics(rows, [], duration_s=4.0)
    assert payload is not None
    assert payload["hands_visible_ratio"] < 0.4
    for metric_id in (
        "gb_gesture_activity_ratio",
        "gb_gesture_space_ratio",
        "gb_self_adaptor_per_min",
        "gb_closed_posture_ratio",
        "gb_gesture_speech_sync",
    ):
        assert payload["metrics"][metric_id]["applicable"] is False
        assert payload["metrics"][metric_id]["value"] is None


def test_audio_only_and_opt_out_are_none():
    rows = _active()
    assert compute_gesture_metrics(rows, [], duration_s=8.0, audio_only=True) is None
    assert (
        compute_gesture_metrics(
            rows, [], duration_s=8.0, accessibility={"prefers_no_video_metrics": True}
        )
        is None
    )


def test_seated_profile_disables_sway_and_locomotion():
    fps = 15.0
    rows = []
    for i in range(int(8 * fps)):
        t = i / fps
        hip = 0.5 + 0.04 * math.sin(2 * math.pi * 0.5 * t)
        rows.append(_row(t, hip_x=hip, speed=0.5, wrist_y=-0.6))
    events = [{"type": "locomotion", "t_start": 1.0, "t_end": 1.8}]
    payload = compute_gesture_metrics(
        rows,
        events,
        duration_s=8.0,
        accessibility={"seated": True},
        section_boundaries_s=[1.2],
        webcam_framing=False,
    )
    assert payload is not None
    assert payload["metrics"]["gb_sway_index"]["applicable"] is False
    assert payload["metrics"]["gb_purposeful_movement"]["applicable"] is False
    assert payload["metrics"]["gb_gesture_activity_ratio"]["applicable"] is True


def test_one_handed_keeps_activity_with_one_wrist_hidden():
    rows = []
    for i in range(90):
        t = i / 15.0
        speed = 0.8 if int(t) % 2 == 0 else 0.0
        row = _row(t, speed=speed)
        row["wrist_r_vis"] = 0.1
        row["wrist_speed_r"] = 0.0
        rows.append(row)
    payload = compute_gesture_metrics(
        rows, [], duration_s=6.0, accessibility={"one_handed": True}, webcam_framing=False
    )
    assert payload is not None
    assert payload["hands_visible_ratio"] >= 0.4
    assert payload["metrics"]["gb_gesture_activity_ratio"]["applicable"] is True
    assert payload["metrics"]["gb_gesture_activity_ratio"]["value"] > 0.2


def test_webcam_caps_confidence_and_drops_sway():
    rows = _active()
    for row in rows:
        row["hip_visible"] = 0.0
    payload = compute_gesture_metrics(rows, [], duration_s=8.0, webcam_framing=True)
    assert payload is not None
    assert payload["webcam_framing"] is True
    assert payload["metrics"]["gb_gesture_activity_ratio"]["confidence"] <= 0.6
    assert payload["metrics"]["gb_self_adaptor_per_min"]["applicable"] is True
    assert payload["metrics"]["gb_sway_index"]["applicable"] is False
    assert payload["metrics"]["gb_purposeful_movement"]["applicable"] is False


def test_sway_sine_higher_than_still():
    fps = 15.0
    sine = []
    still = []
    for i in range(int(10 * fps)):
        t = i / fps
        sine.append(_row(t, hip_x=0.5 + 0.03 * math.sin(2 * math.pi * 0.5 * t)))
        still.append(_row(t, hip_x=0.5))
    sway_hi = gb_sway_index(sine, [])
    sway_lo = gb_sway_index(still, [])
    assert sway_hi is not None and sway_lo is not None
    assert sway_hi > sway_lo


def test_speech_sync_and_purposeful_movement():
    strokes = [1.0, 2.0, 3.0]
    assert gb_gesture_speech_sync(strokes, [1.05, 4.0]) == pytest.approx(1 / 3, abs=0.01)
    assert gb_gesture_speech_sync(strokes, None) is None
    locos = [
        {"type": "locomotion", "t_start": 10.0, "t_end": 11.0},
        {"type": "locomotion", "t_start": 40.0, "t_end": 41.0},
    ]
    assert gb_purposeful_movement(locos, [10.5]) == pytest.approx(0.5)
    assert gb_purposeful_movement(locos, None) is None
    assert gb_purposeful_movement([], [0.0]) is None


def test_vision_stage_writes_gesture_metrics(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    payload = json.loads((tmp_path / "gesture_metrics.json").read_text())
    for metric_id in UNITS:
        assert metric_id in payload["metrics"]
        assert payload["metrics"][metric_id]["unit"] == UNITS[metric_id]


def test_fusion_scores_gestures_when_vision_present(tmp_path: Path):
    persist_accessibility(tmp_path, {})
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "transcript.json").write_text(
        json.dumps(
            {
                "language": "en",
                "duration": 5.0,
                "segments": [{"id": "S0001", "start": 0.0, "end": 5.0, "text": "Hello there."}],
                "words": [],
            }
        )
    )
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(
        json.dumps({"duration_s": 5, "emphasis_times_s": [0.4]})
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000040",
        output_dir=tmp_path,
        context_type="keynote",
        language="en",
        camera_setup="to_camera",
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["gestures_body"]["applicable"] is True
    assert by_id["gestures_body"]["score"] is not None
    present = {m["id"] for m in result["metrics"]}
    assert "gb_gesture_activity_ratio" in present
    assert by_id["visual_aids"]["applicable"] is False


def test_fusion_na_when_profile_opts_out_of_video(tmp_path: Path):
    persist_accessibility(tmp_path, {"prefers_no_video_metrics": True})
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "transcript.json").write_text(json.dumps({"language": "en", "duration": 5, "segments": []}))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 5}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000041",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        camera_setup="to_camera",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["gestures_body"]["applicable"] is False
    assert "accessibility profile" in (by_id["gestures_body"]["na_reason"] or "").lower()
    assert "gb_gesture_activity_ratio" not in {m["id"] for m in result["metrics"]}


def test_fusion_audio_only_is_na(tmp_path: Path):
    (tmp_path / "consents.json").write_text(json.dumps(CONSENT_ON))
    (tmp_path / "transcript.json").write_text(json.dumps({"language": "en", "duration": 3, "segments": []}))
    (tmp_path / "metrics.json").write_text(json.dumps({"metrics": {}}))
    (tmp_path / "audio_metrics.json").write_text(json.dumps({"duration_s": 3}))
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000042",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        camera_setup="audio_only",
    )
    by_id = {c["id"]: c for c in result["categories"]}
    assert by_id["gestures_body"]["applicable"] is False
    assert "audio-only" in (by_id["gestures_body"]["na_reason"] or "").lower()
