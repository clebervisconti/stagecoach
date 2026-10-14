"""Vision events, quality JSON, and camera-setup mismatch (issue #39)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.consent import VisionDecision
from pipeline.stages.vision import run_vision_stage
from pipeline.vision.events import detect_events
from pipeline.vision.quality import detect_setup, mismatch_scale
from pipeline.vision.synthetic import long_flat_face, scripted_events, two_person_talk

TEST_KEY = bytes.fromhex("11" * 32)

VIDEO = VisionDecision(
    run_pose=True,
    run_hands=True,
    run_face_landmarks=True,
    run_expression_metrics=True,
    keep_raw_landmarks=False,
    skip_reason=None,
)


def test_scripted_events_cover_required_types(tmp_path: Path):
    result = run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    payload = json.loads((tmp_path / "vision_events.json").read_text())
    types = {e["type"] for e in payload["events"]}
    assert payload["emotion_inference"] is False
    assert "happy" not in json.dumps(payload).lower()
    assert "gesture_stroke" in types
    assert "self_adaptor" in types
    assert "crossed_arms" in types
    assert "notes_down" in types
    assert "screen_turn" in types
    assert "locomotion" in types
    assert "smile" in types
    quality = json.loads((tmp_path / "vision_quality.json").read_text())
    for key in (
        "person_visible_ratio",
        "face_visible_ratio",
        "mean_face_height_px",
        "mean_person_height_px",
        "mean_luma",
        "camera_motion",
        "occlusion_ratio",
    ):
        assert key in quality
    assert quality["mean_luma"] is not None
    assert quality["camera_setup"]["declared"] == "to_camera"
    assert result.metrics["event_count"] == len(payload["events"])


def test_smile_and_flat_face_require_expression_consent(tmp_path: Path):
    off = VisionDecision(
        run_pose=True,
        run_hands=True,
        run_face_landmarks=True,
        run_expression_metrics=False,
        keep_raw_landmarks=False,
        skip_reason=None,
    )
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=off,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
    )
    types = {e["type"] for e in json.loads((tmp_path / "vision_events.json").read_text())["events"]}
    assert "smile" not in types
    assert "flat_face" not in types


def test_flat_face_window_on_long_low_expressivity(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=long_flat_face(),
        encryption_key=TEST_KEY,
    )
    types = {e["type"] for e in json.loads((tmp_path / "vision_events.json").read_text())["events"]}
    assert "flat_face" in types


def test_setup_mismatch_relaxes_thresholds():
    detected = detect_setup(
        person_visible_ratio=0.02,
        face_visible_ratio=0.0,
        mean_face_height_px=10,
        mean_person_height_norm=0.05,
        has_video=True,
    )
    assert detected == "screen_recording"
    mismatch, warning, scale = mismatch_scale("to_camera", detected)
    assert mismatch is True
    assert warning
    assert scale > 1.0


def test_mismatch_written_on_emptyish_person(tmp_path: Path):
    frames = two_person_talk(seconds=1.0)
    for frame in frames:
        frame.poses = []
        frame.faces = []
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=frames,
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    quality = json.loads((tmp_path / "vision_quality.json").read_text())
    assert quality["camera_setup"]["mismatch"] is True
    assert quality["camera_setup"]["threshold_scale"] >= 1.0
    assert "person" in (quality["camera_setup"]["warning"] or "").lower() or "visible" in (
        quality["camera_setup"]["warning"] or ""
    ).lower()


def _pose_row(t: float, **fields):
    row = {
        "t": t,
        "wrist_speed_l": 0.05,
        "wrist_speed_r": 0.0,
        "hand_face_dist": 1.0,
        "crossed_arms": 0.0,
        "hip_mid_x": 0.5,
        "hip_mid_y": 0.5,
        "shoulder_width": 0.2,
        "person_visible": 1.0,
    }
    row.update(fields)
    return row


def test_detect_events_direct_stroke():
    rows = [_pose_row(i / 15.0, wrist_speed_l=1.2 if i == 7 else 0.05) for i in range(15)]
    kinds = [e["type"] for e in detect_events(rows, [], expression_metrics=False)]
    assert "gesture_stroke" in kinds


def test_detect_events_direct_pose_and_face_types():
    pose = []
    face = []
    for i in range(45):
        t = i / 15.0
        pose.append(
            _pose_row(
                t,
                hand_face_dist=0.1 if 0.5 <= t <= 1.3 else 1.0,
                crossed_arms=1.0 if 1.5 <= t <= 2.2 else 0.0,
                hip_mid_x=0.5 + (0.2 if t >= 2.4 else 0.0),
            )
        )
        face.append(
            {
                "t": t,
                "pitch_deg": -30.0 if t <= 2.2 else 0.0,
                "yaw_deg": 70.0 if 0.4 <= t <= 1.0 else 0.0,
                "blendshapes": {
                    "mouthSmileLeft": 0.7 if 0.2 <= t <= 0.8 else 0.0,
                    "mouthSmileRight": 0.7 if 0.2 <= t <= 0.8 else 0.0,
                },
            }
        )
    types = {e["type"] for e in detect_events(pose, face, expression_metrics=True)}
    assert "self_adaptor" in types
    assert "crossed_arms" in types
    assert "notes_down" in types
    assert "screen_turn" in types
    assert "locomotion" in types
    assert "smile" in types


def test_quality_json_has_no_emotion_labels(tmp_path: Path):
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO,
        frames=scripted_events(),
        encryption_key=TEST_KEY,
        camera_setup="to_camera",
    )
    blob = (tmp_path / "vision_quality.json").read_text().lower()
    assert "emotion_inference" in blob
    assert json.loads((tmp_path / "vision_quality.json").read_text())["emotion_inference"] is False
    for banned in ("happy", "angry", "nervous", "anxious", "confident", "authenticity"):
        assert banned not in blob
