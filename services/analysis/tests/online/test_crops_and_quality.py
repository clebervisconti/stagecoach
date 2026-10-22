"""Crops and production_quality on synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.layout.crop import write_region_tracks
from pipeline.layout.detect import detect_layout
from pipeline.layout.faces import FaceDetection, FakeFaceDetector
from pipeline.stages.production_quality import run_production_quality

from .generate_online_fixtures import generate_one


def test_crops_from_original_composite(tmp_path: Path):
    video = generate_one("composite_pip_tr", tmp_path)
    layout = detect_layout(
        video,
        tmp_path / "job",
        duration_s=2.0,
        frame_width=1920,
        frame_height=1080,
        detector=FakeFaceDetector([FaceDetection(x=820, y=20, w=90, h=110, score=0.92)]),
        preview_source=video,
    )
    artifacts = write_region_tracks(
        video,
        tmp_path / "job",
        layout,
        frame_width=1920,
        frame_height=1080,
    )
    assert Path(artifacts["camera"]).is_file()
    assert Path(artifacts["screen"]).is_file()
    assert artifacts["camera_px"]["w"] > 0
    assert artifacts["screen_px"]["w"] > artifacts["camera_px"]["w"]


def test_production_quality_writes_metrics(tmp_path: Path):
    video = generate_one("screen_only", tmp_path)
    payload = run_production_quality(
        output_dir=tmp_path,
        media_path=video,
        audio_metrics={"snr_db": 24.0},
        source_height=1080,
    )
    ids = {row["id"] for row in payload["metrics"]}
    assert "pq_snr_db" in ids
    assert "pq_source_height_px" in ids
    written = json.loads((tmp_path / "production_quality.json").read_text())
    assert written["metrics"]
