"""Fixture manifests are committed; generated videos stay out of git (E0-5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from generate_online_fixtures import (
    FACE_ASSET,
    GENERATORS,
    MANIFESTS,
    SPEECH_ASSET,
    generate_all,
    generate_one,
    parse_resolution,
    synthesize_speech,
)

ROOT = Path(__file__).resolve().parent


def test_synthetic_face_asset_is_committed():
    assert FACE_ASSET.is_file()
    assert FACE_ASSET.stat().st_size > 0


def test_synthetic_speech_asset_is_committed():
    speech = synthesize_speech(SPEECH_ASSET)
    assert speech.is_file()
    assert speech.stat().st_size > 0


def test_committed_manifests_cover_required_fixtures():
    for name in ("composite_pip_tr", "screen_only", "camera_only", "no_regions"):
        assert name in GENERATORS
        payload = json.loads((MANIFESTS / name / "manifest.json").read_text())
        assert payload["id"] == name
        assert payload["origin"].startswith("synthetic")
        assert (MANIFESTS / name / "source.mp4").exists() is False


def test_generator_writes_three_videos_to_temp(tmp_path: Path):
    paths = generate_all(tmp_path)
    assert len(paths) == 4
    for path in paths:
        assert path.is_file()
        assert path.stat().st_size > 0
        assert path.suffix == ".mp4"


def test_parse_resolution():
    assert parse_resolution("1920x1080") == (1920, 1080)
    assert parse_resolution("1281x721") == (1280, 720)


def test_duration_and_resolution_overrides(tmp_path: Path):
    dest = generate_one("screen_only", tmp_path, duration=1.0, width=640, height=360)
    written = json.loads(dest.with_name("manifest.json").read_text())
    assert written["duration_s"] == 1.0
    assert written["width"] == 640
    assert written["height"] == 360
    import subprocess

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration",
            "-of",
            "json",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(probe.stdout)
    stream = payload["streams"][0]
    assert int(stream["width"]) == 640
    assert int(stream["height"]) == 360
    assert abs(float(stream.get("duration") or 0) - 1.0) < 0.25


def test_generated_video_has_speech_audio(tmp_path: Path):
    dest = generate_one("composite_pip_tr", tmp_path, duration=2.0, width=640, height=360)
    import subprocess

    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_type,sample_rate",
            "-of",
            "json",
            str(dest),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    assert stream["codec_type"] == "audio"

    vol = subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(dest),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    text = vol.stderr
    assert "mean_volume" in text
    mean_line = [line for line in text.splitlines() if "mean_volume" in line][-1]
    mean_db = float(mean_line.split(":")[-1].replace("dB", "").strip())
    assert mean_db > -50.0
