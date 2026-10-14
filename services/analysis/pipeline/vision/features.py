"""Normalized per-frame pose/face features from landmarks (SPEC §6.5 step 3).

No emotion labels. Blendshape keys are MediaPipe names stored as numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

# MediaPipe Pose (33)
NOSE, L_SHOULDER, R_SHOULDER = 0, 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24

POSE_FPS = 15.0
FACE_HANDS_FPS = 10.0

BLENDSHAPE_SUBSET = (
    "browInnerUp",
    "browOuterUpLeft",
    "browOuterUpRight",
    "browDownLeft",
    "browDownRight",
    "mouthSmileLeft",
    "mouthSmileRight",
    "mouthFrownLeft",
    "mouthFrownRight",
    "cheekSquintLeft",
    "cheekSquintRight",
    "eyeWideLeft",
    "eyeWideRight",
)

EYE_LOOK = (
    "eyeLookInLeft",
    "eyeLookInRight",
    "eyeLookOutLeft",
    "eyeLookOutRight",
    "eyeLookUpLeft",
    "eyeLookUpRight",
    "eyeLookDownLeft",
    "eyeLookDownRight",
)


def should_run_face_hands(
    frame_index: int, pose_fps: float = POSE_FPS, target_fps: float = FACE_HANDS_FPS
) -> bool:
    """True about `target_fps` times per second on a `pose_fps` stream."""
    bucket = int(round(frame_index * target_fps / pose_fps))
    prev = int(round((frame_index - 1) * target_fps / pose_fps)) if frame_index else -1
    return bucket != prev


def rotation_to_ypr(matrix: np.ndarray) -> tuple[float, float, float]:
    """Yaw, pitch, roll in degrees from a 4x4 or 3x3 rotation (heuristic, H)."""
    r = np.asarray(matrix, dtype=np.float64)
    if r.size >= 16:
        r = r.reshape(4, 4)[:3, :3]
    else:
        r = r.reshape(3, 3)
    sy = math.sqrt(r[0, 0] ** 2 + r[1, 0] ** 2)
    yaw = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    pitch = math.degrees(math.atan2(-r[2, 0], sy if sy > 1e-6 else 1e-6))
    roll = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    return yaw, pitch, roll


@dataclass
class PoseInstance:
    xyz: np.ndarray  # (33, 3) image-normalized x,y and z
    vis: np.ndarray  # (33,)
    bbox: Optional[np.ndarray] = None  # [x0,y0,x1,y1]


@dataclass
class FaceInstance:
    xyz: np.ndarray  # (N, 3) N typically 478
    vis: np.ndarray
    bbox: Optional[np.ndarray] = None
    matrix: Optional[np.ndarray] = None
    blendshapes: dict[str, float] = field(default_factory=dict)
    height_px: float = 0.0


@dataclass
class HandInstance:
    xyz: np.ndarray  # (21, 3)
    vis: np.ndarray
    handedness: str = "unknown"
    bbox: Optional[np.ndarray] = None


@dataclass
class FrameDetections:
    t: float
    frame_index: int
    width: int
    height: int
    poses: list[PoseInstance]
    faces: list[FaceInstance]
    hands: list[HandInstance]
    run_face_hands: bool
    luma: Optional[float] = None
    motion: Optional[float] = None


def shoulder_width(xyz: np.ndarray, vis: np.ndarray) -> Optional[float]:
    if vis[L_SHOULDER] < 0.5 or vis[R_SHOULDER] < 0.5:
        return None
    return float(np.linalg.norm(xyz[L_SHOULDER, :2] - xyz[R_SHOULDER, :2]))


def hip_mid(xyz: np.ndarray, vis: np.ndarray) -> Optional[np.ndarray]:
    if vis[L_HIP] < 0.5 or vis[R_HIP] < 0.5:
        if vis[L_SHOULDER] >= 0.5 and vis[R_SHOULDER] >= 0.5:
            return (xyz[L_SHOULDER, :2] + xyz[R_SHOULDER, :2]) / 2.0
        return None
    return (xyz[L_HIP, :2] + xyz[R_HIP, :2]) / 2.0


def pose_frame_features(pose: PoseInstance, prev_wrists: Optional[np.ndarray], dt: float) -> dict[str, Any]:
    xyz, vis = pose.xyz, pose.vis
    sw = shoulder_width(xyz, vis) or 1e-6
    mid = hip_mid(xyz, vis)
    wrists = []
    speeds = []
    for idx in (L_WRIST, R_WRIST):
        if vis[idx] < 0.5 or mid is None:
            wrists.append((float("nan"), float("nan")))
            speeds.append(float("nan"))
            continue
        rel = (xyz[idx, :2] - mid) / sw
        wrists.append((float(rel[0]), float(rel[1])))
        if prev_wrists is not None and dt > 0:
            speeds.append(float(np.linalg.norm((xyz[idx, :2] - prev_wrists[idx, :2]) / sw) / dt))
        else:
            speeds.append(0.0)
    face_pt = xyz[NOSE, :2] if vis[NOSE] >= 0.5 else None
    hand_face = float("nan")
    if face_pt is not None:
        dists = []
        for idx in (L_WRIST, R_WRIST):
            if vis[idx] >= 0.5:
                dists.append(float(np.linalg.norm(xyz[idx, :2] - face_pt) / sw))
        if dists:
            hand_face = min(dists)
    bbox = pose.bbox
    crossed = float("nan")
    if vis[L_WRIST] >= 0.5 and vis[R_ELBOW] >= 0.5 and vis[R_WRIST] >= 0.5 and vis[L_ELBOW] >= 0.5:
        d1 = float(np.linalg.norm(xyz[L_WRIST, :2] - xyz[R_ELBOW, :2]) / sw)
        d2 = float(np.linalg.norm(xyz[R_WRIST, :2] - xyz[L_ELBOW, :2]) / sw)
        crossed = 1.0 if d1 < 0.35 and d2 < 0.35 else 0.0
    person_h = float("nan")
    if bbox is not None:
        person_h = float((bbox[3] - bbox[1]) * 1.0)
    return {
        "shoulder_width": sw if sw > 1e-5 else float("nan"),
        "wrist_l_x": wrists[0][0],
        "wrist_l_y": wrists[0][1],
        "wrist_r_x": wrists[1][0],
        "wrist_r_y": wrists[1][1],
        "wrist_speed_l": speeds[0],
        "wrist_speed_r": speeds[1],
        "hand_face_dist": hand_face,
        "hip_mid_x": float(mid[0]) if mid is not None else float("nan"),
        "hip_mid_y": float(mid[1]) if mid is not None else float("nan"),
        "bbox_cx": float((bbox[0] + bbox[2]) / 2) if bbox is not None else float("nan"),
        "bbox_cy": float((bbox[1] + bbox[3]) / 2) if bbox is not None else float("nan"),
        "bbox_w": float(bbox[2] - bbox[0]) if bbox is not None else float("nan"),
        "bbox_h": float(bbox[3] - bbox[1]) if bbox is not None else float("nan"),
        "person_height_norm": person_h,
        "visibility_mean": float(np.mean(vis)),
        "wrist_l_vis": float(vis[L_WRIST]),
        "wrist_r_vis": float(vis[R_WRIST]),
        "crossed_arms": crossed,
        "nose_visible": 1.0 if vis[NOSE] >= 0.5 else 0.0,
        "person_visible": 1.0,
    }
