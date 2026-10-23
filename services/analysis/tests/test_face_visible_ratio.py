"""face_visible_ratio must survive 0.0 and come from the camera crop."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.layout.crop import write_region_tracks
from pipeline.layout.detect import detect_layout
from pipeline.layout.faces import FaceDetection, FakeFaceDetector
from pipeline.stages.fusion_scoring import _first_number, run_fusion_scoring
from pipeline.vision.quality import build_quality

from .online.generate_online_fixtures import generate_one
from .test_fusion_scoring import PACKAGES, _write_inputs


def test_first_number_keeps_zero():
    assert _first_number(0.0, 0.9) == 0.0
    assert _first_number(None, 0.0) == 0.0
    assert _first_number(None, None) is None
    assert _first_number(0.87) == 0.87


def test_fusion_maps_zero_face_ratio(tmp_path: Path):
    _write_inputs(tmp_path, with_content=False, short=True)
    (tmp_path / "vision_quality.json").write_text(
        json.dumps({"face_visible_ratio": 0.0, "person_visible_ratio": 0.0}) + "\n"
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000201",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    assert result["quality"]["face_visible_ratio"] == 0.0


def test_fusion_prefers_camera_crop_yunet_ratio(tmp_path: Path):
    _write_inputs(tmp_path, with_content=False, short=True)
    (tmp_path / "vision_quality.json").write_text(
        json.dumps({"face_visible_ratio": 0.0, "person_visible_ratio": 0.1}) + "\n"
    )
    (tmp_path / "camera_face_quality.json").write_text(
        json.dumps({"face_visible_ratio": 0.875, "source": "yunet_camera_crop"}) + "\n"
    )
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000202",
        output_dir=tmp_path,
        packages_dir=PACKAGES,
        transcript_path=tmp_path / "transcript.json",
        metrics_path=tmp_path / "metrics.json",
        audio_metrics_path=tmp_path / "audio_metrics.json",
    )
    assert result["quality"]["face_visible_ratio"] == 0.875


def test_camera_crop_yunet_ratio_on_composite(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MEDIAPIPE_MODELS_DIR", str(tmp_path / "models"))
    video = generate_one("composite_pip_tr", tmp_path, duration=2.0, width=640, height=360)
    job = tmp_path / "job"
    layout = detect_layout(
        video,
        job,
        duration_s=2.0,
        frame_width=640,
        frame_height=360,
        detector=FakeFaceDetector([FaceDetection(x=810, y=8, w=140, h=100, score=0.93)]),
        preview_source=video,
    )
    assert layout["face_visible_ratio"] == 1.0
    artifacts = write_region_tracks(
        video,
        job,
        layout,
        frame_width=640,
        frame_height=360,
    )
    assert Path(artifacts["camera"]).is_file()
    quality = json.loads((job / "camera_face_quality.json").read_text())
    assert quality["frames_sampled"] > 0
    assert quality["face_visible_ratio"] > 0
    assert quality["source"] == "yunet_camera_crop"

    _write_inputs(job, with_content=False, short=True)
    result = run_fusion_scoring(
        session_id="00000000-0000-4000-8000-000000000203",
        output_dir=job,
        packages_dir=PACKAGES,
        transcript_path=job / "transcript.json",
        metrics_path=job / "metrics.json",
        audio_metrics_path=job / "audio_metrics.json",
    )
    assert result["quality"]["face_visible_ratio"] == quality["face_visible_ratio"]


def test_camera_face_measure_samples_native_width(tmp_path: Path, monkeypatch):
    from pipeline.layout.face_visibility import measure_face_visible_ratio
    from pipeline.layout.sampling import SAMPLE_WIDTH

    clip = tmp_path / "tiny.mp4"
    _write_color_clip(clip, 320, 240)
    seen: dict[str, int] = {}

    def fake_sample(path, *, fps=1.0, width=SAMPLE_WIDTH, max_frames=8):
        seen["width"] = width
        return []

    monkeypatch.setattr("pipeline.layout.face_visibility.sample_frames", fake_sample)
    measure_face_visible_ratio(clip)
    assert seen["width"] == 320
    assert seen["width"] < SAMPLE_WIDTH


def test_composite_pip_tr_camera_crop_face_ratio(tmp_path: Path, monkeypatch):
    """YuNet on the camera crop must see the synthetic face (LION O1 round 3).

    Layout already finds the tile (camera IoU ~0.98). The previous crop path
    stretched camera.mp4 to 960 px so the face left YuNet's 10–300 px band.
    """
    monkeypatch.setenv("MEDIAPIPE_MODELS_DIR", str(tmp_path / "models"))
    video = generate_one("composite_pip_tr", tmp_path)
    job = tmp_path / "job"
    layout = detect_layout(
        video,
        job,
        duration_s=2.0,
        frame_width=1920,
        frame_height=1080,
        delivery_mode="webinar",
        preview_source=video,
    )
    artifacts = write_region_tracks(
        video,
        job,
        layout,
        frame_width=1920,
        frame_height=1080,
    )
    assert Path(artifacts["camera"]).is_file()
    quality = json.loads((job / "camera_face_quality.json").read_text())
    assert quality["frames_sampled"] > 0
    assert quality["source"] == "yunet_camera_crop"
    assert quality["face_visible_ratio"] > 0.5

    from pipeline.layout.face_visibility import measure_face_visible_ratio
    from pipeline.layout.sampling import probe_video_size

    faceless = tmp_path / "faceless.mp4"
    _write_color_clip(faceless, 320, 240)
    assert probe_video_size(faceless) == (320, 240)
    blank = measure_face_visible_ratio(faceless)
    assert blank["frames_sampled"] > 0
    assert blank["face_visible_ratio"] < 0.15


def _write_color_clip(dest: Path, width: int, height: int) -> None:
    import subprocess

    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s={width}x{height}:d=1:r=15",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(dest),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )


def test_build_quality_zero_is_not_none():
    quality = build_quality(
        [{"t": 0.0, "person_visible": 0.0}],
        [],
        [],
        declared_setup="to_camera",
        has_video=True,
    )
    assert quality["face_visible_ratio"] == 0.0
