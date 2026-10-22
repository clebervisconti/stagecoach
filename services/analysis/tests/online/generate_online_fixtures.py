#!/usr/bin/env python3
"""Generate synthetic online-session fixtures (spec §14.2, E0-5).

Produces `composite_pip_tr`, `screen_only`, and `camera_only` with ffmpeg
lavfi. The composite camera tile uses the generated synthetic face in
`fixtures/assets/` (not a real person). Audio is license-clean espeak-ng
speech from `fixtures/assets/synthetic_speech.wav`, not a recording.
No personal data. Video files are written next to committed manifests
only when `--out` is given; they must not be committed.

`--duration` and `--resolution` override the manifest so a 120 s or 60 min
clip can be generated for real-stack timing.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

MANIFESTS = Path(__file__).resolve().parent / "fixtures"
FACE_ASSET = MANIFESTS / "assets" / "synthetic_face.png"
SPEECH_ASSET = MANIFESTS / "assets" / "synthetic_speech.wav"
SPEECH_TEXT = (
    "Welcome to this webinar. Today we will cover three points. "
    "First, the plan. Second, the evidence. Third, the next steps. Thank you."
)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def _even(value: int) -> int:
    """yuv420p requires even width and height."""
    return max(2, value - (value % 2))


def parse_resolution(text: str) -> tuple[int, int]:
    raw = text.lower().replace(" ", "")
    if "x" not in raw:
        raise ValueError(f"resolution must look like 1920x1080, got {text!r}")
    width_s, height_s = raw.split("x", 1)
    width, height = int(width_s), int(height_s)
    if width < 2 or height < 2:
        raise ValueError(f"resolution too small: {text}")
    return _even(width), _even(height)


def synthesize_speech(dest: Path) -> Path:
    """Write the committed espeak-ng clip, or regenerate it when missing."""
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    raw = dest.with_suffix(".espeak.wav")
    try:
        _run(
            [
                "espeak-ng",
                "-v",
                "en-us",
                "-s",
                "145",
                "-w",
                str(raw),
                SPEECH_TEXT,
            ]
        )
        _run(
            [
                "ffmpeg",
                "-i",
                str(raw),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                "-y",
                str(dest),
            ]
        )
    finally:
        raw.unlink(missing_ok=True)
    return dest


def _mux_speech(dest: Path, duration: float) -> None:
    """Loop the synthetic speech clip to cover `duration` (no silence)."""
    speech = synthesize_speech(SPEECH_ASSET)
    tmp = dest.with_suffix(".vid.mp4")
    dest.replace(tmp)
    _run(
        [
            "ffmpeg",
            "-i",
            str(tmp),
            "-stream_loop",
            "-1",
            "-i",
            str(speech),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-t",
            str(duration),
            "-y",
            str(dest),
        ]
    )
    tmp.unlink(missing_ok=True)


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
    _mux_speech(dest, duration)


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
    _mux_speech(dest, duration)


def write_composite_pip_tr(dest: Path, duration: float, width: int, height: int, fps: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not FACE_ASSET.is_file():
        raise FileNotFoundError(
            f"synthetic face asset missing: {FACE_ASSET}. See tests/online/fixtures/README.md"
        )
    tile_w = _even(int(width * 0.1667))
    tile_h = _even(int(height * 0.2222))
    _run(
        [
            "ffmpeg",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x1a1a2e:s={width}x{height}:d={duration}:r={fps}",
            "-loop",
            "1",
            "-i",
            str(FACE_ASSET),
            "-filter_complex",
            (
                "[0:v]drawtext=text='Slide 1':fontcolor=white:fontsize=72:"
                f"x=80:y=80[bg];[1:v]scale={tile_w}:{tile_h},format=yuv420p[tile];"
                "[bg][tile]overlay=x=main_w-overlay_w:y=0"
            ),
            "-t",
            str(duration),
            "-pix_fmt",
            "yuv420p",
            "-c:v",
            "libx264",
            "-y",
            str(dest),
        ]
    )
    _mux_speech(dest, duration)


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
    _mux_speech(dest, duration)


GENERATORS = {
    "screen_only": write_screen_only,
    "camera_only": write_camera_only,
    "composite_pip_tr": write_composite_pip_tr,
    "no_regions": write_no_regions,
}


def generate_one(
    fixture_id: str,
    out_dir: Path,
    *,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Path:
    manifest_path = MANIFESTS / fixture_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    dest = out_dir / fixture_id / "source.mp4"
    duration_s = float(duration if duration is not None else manifest["duration_s"])
    frame_w = _even(int(width if width is not None else manifest["width"]))
    frame_h = _even(int(height if height is not None else manifest["height"]))
    GENERATORS[fixture_id](
        dest,
        duration_s,
        frame_w,
        frame_h,
        int(manifest["fps"]),
    )
    written = dict(manifest)
    written["duration_s"] = duration_s
    written["width"] = frame_w
    written["height"] = frame_h
    dest.with_name("manifest.json").write_text(json.dumps(written, indent=2) + "\n")
    return dest


def generate_all(
    out_dir: Path,
    *,
    duration: float | None = None,
    width: int | None = None,
    height: int | None = None,
) -> list[Path]:
    return [
        generate_one(name, out_dir, duration=duration, width=width, height=height)
        for name in GENERATORS
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="Directory for generated videos")
    parser.add_argument(
        "--only",
        choices=sorted(GENERATORS),
        action="append",
        help="Generate a subset (repeatable)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Override manifest duration_s (use 120 or 3600 for real-stack timing)",
    )
    parser.add_argument(
        "--resolution",
        type=str,
        help="Override WxH, e.g. 1920x1080 or 1280x720",
    )
    args = parser.parse_args()
    width = height = None
    if args.resolution:
        width, height = parse_resolution(args.resolution)
    names = args.only or list(GENERATORS)
    for name in names:
        path = generate_one(name, args.out, duration=args.duration, width=width, height=height)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
