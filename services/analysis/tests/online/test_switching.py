"""Layout runs split when the framing changes, and stay one segment when it does not."""

import subprocess
from pathlib import Path

import numpy as np
import pytest

from pipeline.layout.detect import _classify_frames, detect_layout
from pipeline.layout.faces import FaceDetection
from pipeline.layout.switching import mark_from_faces, stable_runs


def _mark(kind: str, t: float):
    from pipeline.layout.switching import FrameMark

    return FrameMark(t, kind, (0.0, 0.0) if kind != "composite" else (0.8, 0.1))


def test_short_recording_stays_one_segment():
    marks = [_mark("composite", 0), _mark("camera_full", 2)]
    assert stable_runs(marks) == [(0, 2)]


def test_stable_runs_split_a_sustained_change():
    marks = [_mark("composite", index * 2) for index in range(5)]
    marks += [_mark("camera_full", 10 + index * 2) for index in range(5)]
    assert stable_runs(marks) == [(0, 5), (5, 10)]


def test_gallery_uses_one_camera_and_marks_the_rest_other():
    faces = [
        FaceDetection(x=10, y=20, w=70, h=80, score=0.96),
        FaceDetection(x=240, y=20, w=70, h=80, score=0.9),
        FaceDetection(x=470, y=180, w=70, h=80, score=0.62),
    ]
    assert mark_from_faces(0, faces, 640, 360).kind == "gallery"
    frame = type("Frame", (), {"bgr": np.zeros((360, 640, 3), dtype=np.uint8), "t": 0})()
    kind, regions, _confidence, reason = _classify_frames(
        [frame, frame, frame, frame],
        [faces, faces, faces, faces],
        frame_width=640,
        frame_height=360,
        delivery_mode="webinar",
        review_reason=None,
    )
    assert kind == "gallery"
    assert regions[0]["role"] == "camera"
    assert {region["role"] for region in regions[1:]} == {"other_participant"}
    assert reason == "primary_speaker_unclear"


def test_close_scores_are_not_a_gallery_when_faces_do_not_spread():
    faces = [
        FaceDetection(x=10, y=10, w=40, h=40, score=0.9),
        FaceDetection(x=20, y=12, w=40, h=40, score=0.8),
        FaceDetection(x=18, y=16, w=40, h=40, score=0.7),
    ]
    assert mark_from_faces(0, faces, 640, 360).kind != "gallery"


def test_detect_layout_splits_when_the_framing_changes(tmp_path: Path):
    video = tmp_path / "switch.mp4"
    built = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360:d=16:r=5",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        capture_output=True,
    )
    if built.returncode != 0:
        pytest.skip("ffmpeg lavfi is not available")

    class Switching:
        def __init__(self) -> None:
            self.n = 0

        def detect(self, frame):
            self.n += 1
            height, width = frame.shape[:2]
            if self.n <= 4:
                return [FaceDetection(x=width * 0.78, y=8, w=width * 0.12, h=height * 0.12, score=0.93)]
            return [FaceDetection(x=width * 0.15, y=height * 0.08, w=width * 0.4, h=height * 0.7, score=0.95)]

    layout = detect_layout(
        video,
        tmp_path / "job",
        duration_s=16,
        frame_width=640,
        frame_height=360,
        delivery_mode="webinar",
        detector=Switching(),
    )
    assert len(layout["segments"]) >= 2
    kinds = {segment["kind"] for segment in layout["segments"]}
    assert "camera_full" in kinds
    assert layout["segments"][0]["t_start"] == 0
    assert layout["segments"][-1]["t_end"] == pytest.approx(16, abs=0.5)
    assert (tmp_path / "job" / "layout_preview" / "segment_000.jpg").is_file()
    assert (tmp_path / "job" / "layout_preview" / "segment_001.jpg").is_file()
