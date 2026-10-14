"""Slide-change detection with PySceneDetect (BSD-3-Clause) [S47].

AdaptiveDetector threshold 3.0 or ContentDetector 27.0. Merge changes < 2 s
(animations and builds, H). ffmpeg `select='gt(scene,0.3)'` is the fallback.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MERGE_GAP_S = 2.0
CONTENT_THRESHOLD = 27.0
ADAPTIVE_THRESHOLD = 3.0


def merge_short_scenes(scenes: list[tuple[float, float]], min_s: float = MERGE_GAP_S) -> list[tuple[float, float]]:
    """Merge adjacent segments shorter than `min_s` into the previous scene."""
    if not scenes:
        return []
    out: list[list[float]] = [[scenes[0][0], scenes[0][1]]]
    for start, end in scenes[1:]:
        dur = end - start
        if dur < min_s:
            out[-1][1] = end
        else:
            out.append([start, end])
    return [(a, b) for a, b in out if b - a > 0.05]


def detect_scenes_pyscenedetect(
    video_path: Path,
    *,
    start_s: float = 0.0,
    end_s: Optional[float] = None,
    crop: Optional[dict[str, int]] = None,
) -> Optional[list[tuple[float, float]]]:
    """Return [(start_s, end_s), ...] or None if PySceneDetect is unavailable."""
    try:
        from scenedetect import ContentDetector, SceneManager, open_video
    except ImportError:
        logger.info("PySceneDetect not importable; using ffmpeg fallback")
        return None
    try:
        video = open_video(str(video_path))
        manager = SceneManager()
        # ContentDetector(27.0) is the SPEC default. AdaptiveDetector(3.0) is
        # equivalent BSD code in the same package; ContentDetector is stable on
        # short synthetic clips without a stats file.
        manager.add_detector(ContentDetector(threshold=CONTENT_THRESHOLD))
        manager.detect_scenes(video)
        pairs = manager.get_scene_list()
        out: list[tuple[float, float]] = []
        for start, finish in pairs:
            s = float(start.get_seconds())
            e = float(finish.get_seconds())
            if end_s is not None and s >= end_s:
                continue
            if e <= start_s:
                continue
            out.append((max(s, start_s), e if end_s is None else min(e, end_s)))
        return out
    except Exception:
        logger.exception("PySceneDetect failed")
        return None


def detect_scenes_ffmpeg(video_path: Path) -> list[tuple[float, float]]:
    """ffmpeg scene-score fallback (SPEC: select='gt(scene,0.3)')."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "frame=pts_time,pkt_pts_time",
        "-of",
        "csv=p=0",
        "-f",
        "lavfi",
        f"movie={video_path},select='gt(scene,0.3)'",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    times = []
    for line in result.stdout.splitlines():
        part = line.split(",")[0].strip()
        try:
            times.append(float(part))
        except ValueError:
            continue
    if not times:
        return []
    duration = _duration(video_path)
    bounds = [0.0, *times, duration]
    scenes = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    return scenes


def _duration(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def detect_scenes(
    video_path: Path,
    *,
    crop: Optional[dict[str, int]] = None,
    duration_s: Optional[float] = None,
) -> dict[str, Any]:
    pyscene = detect_scenes_pyscenedetect(video_path, crop=crop)
    engine = "pyscenedetect"
    scenes = pyscene
    if not scenes:
        scenes = detect_scenes_ffmpeg(video_path)
        engine = "ffmpeg_scene_0.3"
    if not scenes:
        dur = duration_s if duration_s is not None else _duration(video_path)
        scenes = [(0.0, max(dur, 0.1))]
        engine = "single_span"
    merged = merge_short_scenes(scenes, MERGE_GAP_S)
    return {"engine": engine, "raw_count": len(scenes), "scenes": merged}
