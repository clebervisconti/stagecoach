"""Vision stage: tracking, smoothing, aggregates, consent, no OpenFace (issue #38)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.consent import VisionDecision, decide_vision, run_vision_if_allowed
from pipeline.vision.aggregate import FACE_BASE_COLUMNS, POSE_COLUMNS, read_encrypted_parquet
from pipeline.vision.crypto import MAGIC, is_encrypted
from pipeline.vision.features import FACE_HANDS_FPS, POSE_FPS, should_run_face_hands
from pipeline.vision.models import MODEL_REGISTRY
from pipeline.vision.one_euro import OneEuroFilter
from pipeline.vision.smoothing import savitzky_golay
from pipeline.vision.synthetic import two_person_talk
from pipeline.vision.tracking import PrimaryTracker, bbox_from_landmarks, iou
from pipeline.stages.vision import run_vision_stage

TEST_KEY = bytes.fromhex("11" * 32)

VIDEO_ON = VisionDecision(
    run_pose=True,
    run_hands=True,
    run_face_landmarks=True,
    run_expression_metrics=False,
    keep_raw_landmarks=False,
    skip_reason=None,
)


def _snapshot(**granted: bool) -> dict:
    purposes = {
        name: {"granted": False}
        for name in (
            "video_analysis",
            "expression_analysis",
            "keep_detailed_tracking",
            "research_use",
            "benchmarks",
        )
    }
    for name, value in granted.items():
        purposes[name]["granted"] = value
    return {"policy_id": "1.0.0", "purposes": purposes}


def test_one_euro_damps_impulse():
    filt = OneEuroFilter(min_cutoff=1.0, beta=0.007)
    times = np.linspace(0, 1, 16)
    values = [filt(float(t), 0.0 if i != 8 else 1.0) for i, t in enumerate(times)]
    assert max(values) < 0.6


def test_savgol_reduces_high_freq_jitter():
    rng = np.random.default_rng(0)
    x = np.sin(np.linspace(0, 2 * np.pi, 30)) + rng.normal(0, 0.2, 30)
    y = savitzky_golay(x)
    assert np.std(np.diff(y)) < np.std(np.diff(x))


def test_iou_and_primary_person_is_larger_central():
    a = np.array([0.3, 0.3, 0.7, 0.8])
    b = np.array([0.32, 0.32, 0.68, 0.78])
    c = np.array([0.0, 0.6, 0.2, 0.9])
    assert iou(a, b) > 0.5
    assert iou(a, c) < 0.1
    tracker = PrimaryTracker()
    for i in range(10):
        tracker.update([a, c], i)
    assert tracker.primary_id is not None
    # First detection is the large central box; it should win persistence+size.
    ids = tracker.update([a, c], 10)
    assert ids[0] == tracker.primary_id


def test_face_hands_sampling_is_10_of_15():
    flags = [should_run_face_hands(i) for i in range(15)]
    assert flags[0] is True
    assert sum(flags) == 10


def test_bbox_from_landmarks_needs_visible_points():
    xy = np.array([[0.1, 0.1], [0.2, 0.2], [0.3, 0.4]], dtype=np.float64)
    vis = np.array([0.9, 0.9, 0.9])
    box = bbox_from_landmarks(xy, vis)
    assert box is not None
    assert box[2] > box[0]


def test_consent_skips_without_calling_stage(tmp_path: Path):
    calls = []

    def runner(decision):
        calls.append(decision)
        return run_vision_stage(
            output_dir=tmp_path,
            session_id="s",
            decision=decision,
            frames=two_person_talk(seconds=1.0),
            encryption_key=TEST_KEY,
        ).to_dict()

    denied = run_vision_if_allowed(_snapshot(), runner)
    assert denied["called"] is False
    assert calls == []
    assert not (tmp_path / "pose.parquet").exists()

    allowed = run_vision_if_allowed(_snapshot(video_analysis=True), runner)
    assert allowed["called"] is True
    assert (tmp_path / "pose.parquet").exists()


def test_aggregates_encrypted_and_raw_discarded(tmp_path: Path):
    frames = two_person_talk(seconds=2.0)
    result = run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO_ON,
        frames=frames,
        encryption_key=TEST_KEY,
    )
    pose_path = tmp_path / "pose.parquet"
    face_path = tmp_path / "face.parquet"
    assert pose_path.exists() and face_path.exists()
    assert is_encrypted(pose_path)
    assert pose_path.read_bytes()[:6] == MAGIC
    assert pose_path.read_bytes()[:4] != b"PAR1"
    table = read_encrypted_parquet(pose_path, TEST_KEY)
    for col in POSE_COLUMNS:
        assert col in table.column_names
    assert table.num_rows >= 2
    vis = table.column("person_visible_ratio").to_pylist()
    assert max(vis) > 0.5
    assert not (tmp_path / "landmarks.parquet").exists()
    assert result.metrics["openface_used"] is False
    assert result.metrics["cpu_only"] is True
    assert result.metrics["emotion_inference"] is False
    assert list(tmp_path.glob("*.png")) == []
    assert list(tmp_path.glob("*.jpg")) == []
    metrics = json.loads((tmp_path / "vision_metrics.json").read_text())
    assert metrics["pose_fps"] == POSE_FPS
    assert metrics["face_hands_fps"] == FACE_HANDS_FPS
    assert metrics["pose_frames"] == 30
    assert metrics["face_frames"] == 20
    face_table = read_encrypted_parquet(face_path, TEST_KEY)
    for col in FACE_BASE_COLUMNS:
        assert col in face_table.column_names
    assert "mouthSmileLeft" not in face_table.column_names


def test_keep_detailed_tracking_writes_raw_landmarks(tmp_path: Path):
    decision = VisionDecision(
        run_pose=True,
        run_hands=True,
        run_face_landmarks=True,
        run_expression_metrics=False,
        keep_raw_landmarks=True,
        skip_reason=None,
    )
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=decision,
        frames=two_person_talk(seconds=1.0),
        encryption_key=TEST_KEY,
    )
    raw = tmp_path / "landmarks.parquet"
    assert raw.exists()
    assert is_encrypted(raw)
    table = read_encrypted_parquet(raw, TEST_KEY)
    assert "x" in table.column_names
    assert table.num_rows > 0


def test_expression_opt_in_adds_blendshape_columns(tmp_path: Path):
    decision = VisionDecision(
        run_pose=True,
        run_hands=True,
        run_face_landmarks=True,
        run_expression_metrics=True,
        keep_raw_landmarks=False,
        skip_reason=None,
    )
    run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=decision,
        frames=two_person_talk(seconds=1.0),
        encryption_key=TEST_KEY,
    )
    face = read_encrypted_parquet(tmp_path / "face.parquet", TEST_KEY)
    assert "mouthSmileLeft" in face.column_names
    assert "happy" not in face.column_names
    assert "emotion" not in face.column_names


def test_no_video_skips(tmp_path: Path):
    result = run_vision_stage(
        output_dir=tmp_path,
        session_id="s",
        decision=VIDEO_ON,
        video_path=tmp_path / "missing.mp4",
        encryption_key=TEST_KEY,
    )
    assert result.skipped is True
    assert result.skip_reason == "no_video_stream"


def test_openface_not_a_dependency():
    req = (Path(__file__).parent.parent / "requirements.txt").read_text().lower()
    assert "openface" not in req
    registry = json.loads(
        (Path(__file__).parent.parent / "models" / "model_registry.json").read_text()
    )
    assert registry["openface_used"] is False
    assert registry["emotion_inference"] is False
    assert registry["cpu_only"] is True
    for model in MODEL_REGISTRY:
        assert model["license"] == "Apache-2.0"
        assert model["delegate"] == "CPU"
        assert "Apache" in model["license_evidence"]


def test_vision_source_has_no_emotion_classifier_or_openface():
    root = Path(__file__).parent.parent / "pipeline"
    for path in root.rglob("*.py"):
        text = path.read_text()
        lowered = text.lower()
        assert "import openface" not in lowered
        assert "from openface" not in lowered
        assert "you were happy" not in lowered
        assert "you looked bored" not in lowered
        assert "emotion_classifier" not in lowered


def test_licenses_are_apache_for_models():
    for model in MODEL_REGISTRY:
        assert model["sha256"]
        assert len(model["sha256"]) == 64
        assert model["url"].startswith("https://storage.googleapis.com/mediapipe-models/")
