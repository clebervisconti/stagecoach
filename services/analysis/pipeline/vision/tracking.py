"""Primary-person tracking by IoU (SPEC §6.5).

Largest, most central, most persistent pose is the primary speaker.
Re-identification across frames uses greedy IoU matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

IOU_MATCH = 0.3  # heuristic (H)


def bbox_from_landmarks(xy: np.ndarray, vis: np.ndarray, min_vis: float = 0.5) -> Optional[np.ndarray]:
    """Return [x0, y0, x1, y1] in normalized image coords, or None."""
    mask = vis >= min_vis
    if int(mask.sum()) < 3:
        return None
    pts = xy[mask]
    x0, y0 = float(pts[:, 0].min()), float(pts[:, 1].min())
    x1, y1 = float(pts[:, 0].max()), float(pts[:, 1].max())
    if x1 <= x0 or y1 <= y0:
        return None
    return np.array([x0, y0, x1, y1], dtype=np.float64)


def iou(a: np.ndarray, b: np.ndarray) -> float:
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix1 - ix0), max(0.0, iy1 - iy0)
    inter = iw * ih
    area_a = max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])
    area_b = max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    denom = area_a + area_b - inter
    if denom <= 0:
        return 0.0
    return float(inter / denom)


def _area(box: np.ndarray) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _center_score(box: np.ndarray) -> float:
    cx = 0.5 * (box[0] + box[2])
    cy = 0.5 * (box[1] + box[3])
    dist = math_hypot(cx - 0.5, cy - 0.5)
    return max(0.0, 1.0 - dist / 0.75)


def math_hypot(x: float, y: float) -> float:
    return float(np.hypot(x, y))


@dataclass
class Track:
    track_id: int
    bbox: np.ndarray
    hits: int = 0
    missed: int = 0
    score: float = 0.0
    last_index: int = -1


@dataclass
class PrimaryTracker:
    """Greedy IoU tracker; primary = max accumulated size×center×persistence."""

    iou_threshold: float = IOU_MATCH
    max_missed: int = 8
    _next_id: int = 0
    tracks: dict[int, Track] = field(default_factory=dict)
    _primary_id: Optional[int] = None

    def update(self, boxes: list[np.ndarray], frame_index: int) -> list[int]:
        """Assign a track id to each detection box. Returns ids aligned with boxes."""
        assigned = [-1] * len(boxes)
        used_tracks: set[int] = set()
        used_dets: set[int] = set()
        pairs: list[tuple[float, int, int]] = []
        for di, box in enumerate(boxes):
            for tid, track in self.tracks.items():
                pairs.append((iou(track.bbox, box), di, tid))
        pairs.sort(reverse=True)
        for score, di, tid in pairs:
            if score < self.iou_threshold or di in used_dets or tid in used_tracks:
                continue
            assigned[di] = tid
            used_dets.add(di)
            used_tracks.add(tid)
        for di, box in enumerate(boxes):
            if assigned[di] >= 0:
                continue
            tid = self._next_id
            self._next_id += 1
            self.tracks[tid] = Track(track_id=tid, bbox=box.copy())
            assigned[di] = tid
            used_tracks.add(tid)
        present = set(i for i in assigned if i >= 0)
        for tid, track in list(self.tracks.items()):
            if tid in present:
                continue
            track.missed += 1
            if track.missed > self.max_missed:
                del self.tracks[tid]
        for di, box in enumerate(boxes):
            tid = assigned[di]
            track = self.tracks[tid]
            track.bbox = box.copy()
            track.hits += 1
            track.missed = 0
            track.last_index = frame_index
            track.score += _area(box) * _center_score(box)
        if self.tracks:
            self._primary_id = max(self.tracks.values(), key=lambda t: t.score).track_id
        return assigned

    @property
    def primary_id(self) -> Optional[int]:
        return self._primary_id
