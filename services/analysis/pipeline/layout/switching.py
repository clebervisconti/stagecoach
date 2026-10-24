"""Temporal layout runs for recordings whose framing changes (spec §9.2)."""

from __future__ import annotations

from dataclasses import dataclass

from pipeline.layout.faces import FaceDetection

# Same full-frame threshold as detect.py. A face this tall is the whole shot.
FACE_FULL_RATIO = 0.28
MIN_RUN_SAMPLES = 3


@dataclass(frozen=True)
class FrameMark:
    t: float
    kind: str
    bucket: tuple[float, float]


def mark_from_faces(t: float, faces: list[FaceDetection], width: int, height: int) -> FrameMark:
    """Coarse signature. Gallery needs several faces spread across the frame."""
    if width <= 0 or height <= 0:
        return FrameMark(t, "no_video", (0.0, 0.0))
    if len(faces) >= 3 and _spread(faces, width, height):
        return FrameMark(t, "gallery", (0.0, 0.0))
    if not faces:
        return FrameMark(t, "screen_full", (0.0, 0.0))
    face = max(faces, key=lambda item: item.score)
    if (face.h / height) >= FACE_FULL_RATIO:
        return FrameMark(t, "camera_full", (0.0, 0.0))
    center_x = round(((face.x + face.w / 2) / width) / 0.1) * 0.1
    center_y = round(((face.y + face.h / 2) / height) / 0.1) * 0.1
    return FrameMark(t, "composite", (center_x, center_y))


def _spread(faces: list[FaceDetection], width: int, height: int) -> bool:
    xs = [(face.x + face.w / 2) / width for face in faces]
    ys = [(face.y + face.h / 2) / height for face in faces]
    return (max(xs) - min(xs)) >= 0.25 or (max(ys) - min(ys)) >= 0.25


def stable_runs(marks: list[FrameMark], min_samples: int = MIN_RUN_SAMPLES) -> list[tuple[int, int]]:
    """Half-open index ranges. Runs shorter than `min_samples` fold into a neighbour.

    A short recording (fewer samples than `min_samples`) stays one segment, which
    keeps the O1 single-layout fixtures on one segment.
    """
    if not marks:
        return []
    raw: list[tuple[int, int]] = []
    start = 0
    for index in range(1, len(marks) + 1):
        changed = index == len(marks) or (marks[index].kind, marks[index].bucket) != (
            marks[start].kind,
            marks[start].bucket,
        )
        if changed:
            raw.append((start, index))
            start = index
    if len(marks) < min_samples:
        return [(0, len(marks))]

    merged: list[tuple[int, int]] = []
    index = 0
    while index < len(raw):
        begin, end = raw[index]
        short = end - begin < min_samples
        if short and merged:
            prev_begin, _prev_end = merged[-1]
            merged[-1] = (prev_begin, end)
        elif short and index + 1 < len(raw):
            _next_begin, next_end = raw[index + 1]
            raw[index + 1] = (begin, next_end)
        else:
            merged.append((begin, end))
        index += 1
    return merged or [(0, len(marks))]
