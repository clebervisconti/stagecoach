#!/usr/bin/env python3
"""Generate synthetic online-session fixtures (spec §14.2, E0-5).

Produces `composite_pip_tr`, `screen_only`, and `camera_only` with ffmpeg
lavfi. No personal data. Video files are written next to committed manifests
only when `--out` is given; they must not be committed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

MANIFESTS = Path(__file__).resolve().parent / "fixtures"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def write_screen_only(dest: Path, duration: float, width: int, height: int, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s={width}x{height}:d={duration}:r={fps}",
            "-vf",
            "drawtext=text='Agenda':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=h/3",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-y",
            str(dest),
        ]
    )


def write_camera_only(dest: Path, duration: float, width: int, height: int, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x2b2b2b:s={width}x{height}:d={duration}:r={fps}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0xc68642:s=200x240:d={duration}:r={fps}",
            "-filter_complex",
            "[1:v]format=yuv420p[tile];[0:v][tile]overlay=x='(W-w)/2+20*sin(2*PI*t)':y='(H-h)/2'",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-y",
            str(dest),
        ]
    )


def write_composite_pip_tr(dest: Path, duration: float, width: int, height: int, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tile_w = int(width * 0.1667)
    tile_h = int(height * 0.2222)
    _run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s={width}x{height}:d={duration}:r={fps}",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0xc68642:s={tile_w}x{tile_h}:d={duration}:r={fps}",
            "-filter_complex",
            (
                "[0:v]drawtext=text='Slide 1':fontcolor=white:fontsize=72:"
                "x=80:y=80[bg];[1:v]format=yuv420p[tile];"
                "[bg][tile]overlay=x=main_w-overlay_w:y=0"
            ),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-y",
            str(dest),
        ]
    )


def write_no_regions(dest: Path, duration: float, width: int, height: int, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s={width}x{height}:d={duration}:r={fps}",
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-y",
            str(dest),
        ]
    )


GENERATORS = {
    "screen_only": write_screen_only,
    "camera_only": write_camera_only,
    "composite_pip_tr": write_composite_pip_tr,
    "no_regions": write_no_regions,
}


def generate_one(fixture_id: str, out_dir: Path) -> Path:
    manifest_path = MANIFESTS / fixture_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    dest = out_dir / fixture_id / "source.mp4"
    GENERATORS[fixture_id](
        dest,
        float(manifest["duration_s"]),
        int(manifest["width"]),
        int(manifest["height"]),
        int(manifest["fps"]),
    )
    dest.with_name("manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return dest


def generate_all(out_dir: Path) -> list[Path]:
    return [generate_one(name, out_dir) for name in GENERATORS]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Directory for generated videos")
    parser.add_argument(
        "--only",
        choices=sorted(GENERATORS),
        action="append",
        help="Generate a subset (repeatable)",
    )
    args = parser.parse_args()
    names = args.only or list(GENERATORS)
    for name in names:
        path = generate_one(name, args.out)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
