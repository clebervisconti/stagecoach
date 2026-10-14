"""Synthetic detections for tests (generated geometry, not a recording)."""

from __future__ import annotations

import numpy as np

from pipeline.vision.features import (
    FACE_HANDS_FPS,
    POSE_FPS,
    FaceInstance,
    FrameDetections,
    HandInstance,
    PoseInstance,
    should_run_face_hands,
)
from pipeline.vision.tracking import bbox_from_landmarks


def _pose_template(cx: float, cy: float, scale: float, jitter: float, rng: np.random.Generator) -> PoseInstance:
    xyz = np.zeros((33, 3), dtype=np.float64)
    vis = np.ones(33, dtype=np.float64)
    # Rough standing figure in normalized coords.
    xyz[0] = [cx, cy - 0.22 * scale, 0]
    xyz[11] = [cx - 0.10 * scale, cy - 0.08 * scale, 0]
    xyz[12] = [cx + 0.10 * scale, cy - 0.08 * scale, 0]
    xyz[13] = [cx - 0.16 * scale, cy + 0.02 * scale, 0]
    xyz[14] = [cx + 0.16 * scale, cy + 0.02 * scale, 0]
    xyz[15] = [cx - 0.18 * scale, cy + 0.12 * scale, 0]
    xyz[16] = [cx + 0.18 * scale, cy + 0.12 * scale, 0]
    xyz[23] = [cx - 0.06 * scale, cy + 0.18 * scale, 0]
    xyz[24] = [cx + 0.06 * scale, cy + 0.18 * scale, 0]
    xyz += rng.normal(0.0, jitter, xyz.shape)
    bbox = bbox_from_landmarks(xyz[:, :2], vis)
    return PoseInstance(xyz=xyz, vis=vis, bbox=bbox)


def _face_template(cx: float, cy: float, scale: float) -> FaceInstance:
    xyz = np.zeros((10, 3), dtype=np.float64)
    vis = np.ones(10, dtype=np.float64)
    xyz[:, 0] = cx + np.linspace(-0.03, 0.03, 10) * scale
    xyz[:, 1] = cy - 0.22 * scale + np.linspace(-0.02, 0.02, 10) * scale
    bbox = bbox_from_landmarks(xyz[:, :2], vis)
    matrix = np.eye(4, dtype=np.float64)
    return FaceInstance(
        xyz=xyz,
        vis=vis,
        bbox=bbox,
        matrix=matrix,
        blendshapes={"mouthSmileLeft": 0.1, "mouthSmileRight": 0.1, "eyeLookInLeft": 0.0},
        height_px=80.0 * scale,
    )


def _hand_template(wx: float, wy: float) -> HandInstance:
    xyz = np.zeros((21, 3), dtype=np.float64)
    vis = np.ones(21, dtype=np.float64)
    xyz[:, 0] = wx + np.linspace(0, 0.02, 21)
    xyz[:, 1] = wy + np.linspace(0, 0.02, 21)
    return HandInstance(xyz=xyz, vis=vis, handedness="Left", bbox=bbox_from_landmarks(xyz[:, :2], vis))


def two_person_talk(
    seconds: float = 2.0,
    fps: float = POSE_FPS,
    width: int = 640,
    height: int = 480,
    seed: int = 0,
) -> list[FrameDetections]:
    """Primary person is larger and more central; a smaller person stands aside."""
    rng = np.random.default_rng(seed)
    n = int(round(seconds * fps))
    frames: list[FrameDetections] = []
    for i in range(n):
        t = i / fps
        # Primary walks a little; secondary stays in the corner.
        primary = _pose_template(0.50 + 0.02 * np.sin(t * 2), 0.50, 1.0, 0.002, rng)
        secondary = _pose_template(0.18, 0.62, 0.55, 0.002, rng)
        run = should_run_face_hands(i, fps, FACE_HANDS_FPS)
        faces: list[FaceInstance] = []
        hands: list[HandInstance] = []
        if run:
            faces = [_face_template(0.50, 0.50, 1.0), _face_template(0.18, 0.62, 0.55)]
            hands = [_hand_template(float(primary.xyz[15, 0]), float(primary.xyz[15, 1]))]
        frames.append(
            FrameDetections(
                t=t,
                frame_index=i,
                width=width,
                height=height,
                poses=[primary, secondary],
                faces=faces,
                hands=hands,
                run_face_hands=run,
            )
        )
    return frames
