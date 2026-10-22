"""Fixture manifests are committed; generated videos stay out of git (E0-5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from generate_online_fixtures import GENERATORS, MANIFESTS, generate_all

ROOT = Path(__file__).resolve().parent


def test_committed_manifests_cover_required_fixtures():
    for name in ("composite_pip_tr", "screen_only", "camera_only"):
        assert name in GENERATORS
        payload = json.loads((MANIFESTS / name / "manifest.json").read_text())
        assert payload["id"] == name
        assert payload["origin"].startswith("synthetic")
        assert (MANIFESTS / name / "source.mp4").exists() is False


def test_generator_writes_three_videos_to_temp(tmp_path: Path):
    paths = generate_all(tmp_path)
    assert len(paths) == 3
    for path in paths:
        assert path.is_file()
        assert path.stat().st_size > 0
        assert path.suffix == ".mp4"
