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
                luma=0.48,
                motion=0.01,
            )
        )
    return frames


def _pitch_matrix(pitch_deg: float, yaw_deg: float = 0.0) -> np.ndarray:
    """Build a 4x4 matching rotation_to_ypr (yaw about Z, pitch about Y)."""
    p = np.deg2rad(pitch_deg)
    y = np.deg2rad(yaw_deg)
    c, s = np.cos(p), np.sin(p)
    rp = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)
    cy, sy = np.cos(y), np.sin(y)
    ry = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]], dtype=np.float64)
    m = np.eye(4, dtype=np.float64)
    m[:3, :3] = ry @ rp
    return m


def scripted_events(seconds: float = 5.0, fps: float = POSE_FPS) -> list[FrameDetections]:
    """Synthetic talk with a stroke, adaptor, crossed arms, notes-down, turn, walk, and smile."""
    rng = np.random.default_rng(1)
    n = int(round(seconds * fps))
    frames: list[FrameDetections] = []
    for i in range(n):
        t = i / fps
        # Scale 1.3 so person height is clearly to-camera after bbox reconstruction.
        # Holds are longer than the event minima so One-Euro + SG still leave ≥ min duration.
        walk = 0.35 if 3.30 <= t <= 4.20 else 0.0
        pose = _pose_template(0.50 + walk, 0.50, 1.3, 0.001, rng)
        if 0.30 <= t <= 0.55:
            # Step-function wrist flick: high instantaneous speed at the edges.
            pose.xyz[16, :2] = pose.xyz[16, :2] + np.array([0.22, -0.14])
        if 0.60 <= t <= 1.90:
            pose.xyz[15, :2] = pose.xyz[0, :2]  # left wrist on face; 1.3 s raw
        if 2.05 <= t <= 3.20:
            pose.xyz[15, :2] = pose.xyz[14, :2]
            pose.xyz[16, :2] = pose.xyz[13, :2]
        run = should_run_face_hands(i, fps, FACE_HANDS_FPS)
        faces: list[FaceInstance] = []
        if run:
            face = _face_template(0.50, 0.50, 1.3)
            pitch = -32.0 if 0.15 <= t <= 2.40 else 0.0
            yaw = 70.0 if 0.90 <= t <= 1.70 else 0.0
            face.matrix = _pitch_matrix(pitch, yaw)
            smile = 0.75 if 0.25 <= t <= 1.05 else 0.04
            face.blendshapes = {
                "mouthSmileLeft": smile,
                "mouthSmileRight": smile,
                "browInnerUp": 0.02,
                "eyeLookInLeft": 0.0,
            }
            faces = [face]
        frames.append(
            FrameDetections(
                t=t,
                frame_index=i,
                width=640,
                height=480,
                poses=[pose],
                faces=faces,
                hands=[],
                run_face_hands=run,
                luma=0.5,
                motion=0.03 if 3.30 <= t <= 4.20 else 0.005,
            )
        )
    return frames


def long_flat_face(seconds: float = 65.0, fps: float = POSE_FPS) -> list[FrameDetections]:
    """Long low-expressivity stretch for flat_face windows (expression opt-in)."""
    rng = np.random.default_rng(2)
    n = int(round(seconds * fps))
    frames: list[FrameDetections] = []
    for i in range(n):
        t = i / fps
        pose = _pose_template(0.5, 0.5, 1.0, 0.001, rng)
        run = should_run_face_hands(i, fps, FACE_HANDS_FPS)
        faces: list[FaceInstance] = []
        if run:
            face = _face_template(0.5, 0.5, 1.0)
            level = 0.4 if t < 2.0 else 0.01
            face.blendshapes = {name: level for name in ("mouthSmileLeft", "browInnerUp", "eyeWideLeft")}
            faces = [face]
        frames.append(
            FrameDetections(
                t=t,
                frame_index=i,
                width=640,
                height=480,
                poses=[pose],
                faces=faces,
                hands=[],
                run_face_hands=run,
                luma=0.4,
                motion=0.0,
            )
        )
    return frames

