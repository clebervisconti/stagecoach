"""Stage wiring: skip reasons, a synthetic file, and no stage-mode step."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline.screen.persist import persist_screen_flow
from pipeline.stages.screen_flow import _screen_offset, run_screen_flow, screen_flow_skip_reason
from tests.online.screen_frames import slide_sequence

WORKER = Path(__file__).resolve().parents[2] / "worker.py"


def test_skip_reasons():
    assert screen_flow_skip_reason("stage", audio_only=False, video_ready=True) == "stage_mode"
    assert screen_flow_skip_reason("webinar", audio_only=True, video_ready=True) == "audio_only_chosen"
    assert screen_flow_skip_reason("webinar", audio_only=False, video_ready=False) == "no_screen"
    assert screen_flow_skip_reason("recorded_video", audio_only=False, video_ready=True) is None


def test_screen_offset_uses_the_longest_span(tmp_path: Path):
    (tmp_path / "screen_spans.json").write_text(
        json.dumps(
            [
                {"t0": 0, "t1": 5, "src_t0": 0},
                {"t0": 5, "t1": 40, "src_t0": 80},
            ]
        ),
        encoding="utf-8",
    )
    assert _screen_offset(tmp_path) == 80.0


def test_persist_skips_when_ids_are_not_uuids(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://stagecoach:stagecoach@127.0.0.1/none")
    persist_screen_flow(
        job_id="job",
        session_id="session",
        document={"version": "1.0.0", "segments": []},
        artifact_uri="screen_flow.json",
    )


def test_worker_runs_screen_flow_only_off_stage():
    source = WORKER.read_text(encoding="utf-8")
    start = source.index('if delivery_mode != "stage":\n            from pipeline.stages.screen_flow import')
    window = source[start:].split("from pipeline.stages.content_llm", 1)[0]
    assert "run_screen_flow(" in window
    assert "stage_mode" not in window


def _write_mp4(path: Path, frames) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("ffmpeg is not installed")
    raw = path.with_suffix(".raw")
    height, width = frames[0].shape
    payload = b"".join(frame.tobytes() * 5 for frame in frames)
    raw.write_bytes(payload)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-s",
            f"{width}x{height}",
            "-r",
            "5",
            "-i",
            str(raw),
            "-c:v",
            "libx264",
            "-g",
            "5",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    raw.unlink()


def test_stage_writes_screen_flow_without_a_judgment(tmp_path: Path):
    video = tmp_path / "screen.mp4"
    _write_mp4(video, slide_sequence())
    transcript = {
        "segments": [
            {
                "id": "s1",
                "words": [
                    {"word": "network", "start": 1.0, "end": 1.4, "probability": 0.2},
                    {"word": "gateway", "start": 6.4, "end": 6.8, "probability": 0.9},
                ],
            }
        ]
    }
    (tmp_path / "transcript.json").write_text(json.dumps(transcript), encoding="utf-8")
    (tmp_path / "alignment.json").write_text(
        json.dumps({"vad_segments": [{"start": 0.0, "end": 3.0, "is_speech": False}, {"start": 5.0, "end": 14.0, "is_speech": True}]}),
        encoding="utf-8",
    )
    outcome = run_screen_flow(
        output_dir=tmp_path,
        session_id="sess",
        job_id="job",
        video_path=video,
        delivery_mode="webinar",
        language="en",
        packages_dir=Path(__file__).resolve().parents[4] / "packages",
        ocr_by_segment=lambda _start, _end: ("network gateway policy review", 4, None),
        deadline_s=30,
    )
    assert outcome.skipped is False
    document = json.loads((tmp_path / "screen_flow.json").read_text(encoding="utf-8"))
    assert document["version"] == "1.0.0"
    assert document["content_judgment"] is False
    assert document["quality"]["asr_dropped_words"] >= 1
    assert (tmp_path / "screen_activity.parquet").is_file()
    assert (tmp_path / "slides.json").is_file()
    slides = json.loads((tmp_path / "slides.json").read_text(encoding="utf-8"))
    assert slides["scene_engine"] in {"ssim", "ssim+pyscenedetect"}
