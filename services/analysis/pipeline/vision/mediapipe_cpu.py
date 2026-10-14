"""CPU MediaPipe Tasks landmarker (VIDEO mode). OpenFace is not imported."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.vision.features import FaceInstance, HandInstance, PoseInstance, should_run_face_hands
from pipeline.vision.models import ensure_models
from pipeline.vision.tracking import bbox_from_landmarks


class CpuLandmarkers:
    """Pose every frame; face + hands at 10 fps. Delegate is CPU."""

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        from mediapipe.tasks.python.core import base_options as mp_base
        from mediapipe.tasks.python import vision as mp_vision

        paths = ensure_models(models_dir)
        running = mp_vision.RunningMode.VIDEO
        delegate = getattr(mp_base.BaseOptions.Delegate, "CPU", None)

        def base(filename: str) -> Any:
            kwargs: dict[str, Any] = {"model_asset_path": str(paths[filename])}
            if delegate is not None:
                kwargs["delegate"] = delegate
            return mp_base.BaseOptions(**kwargs)

        self._pose = mp_vision.PoseLandmarker.create_from_options(
            mp_vision.PoseLandmarkerOptions(
                base_options=base("pose_landmarker_full.task"),
                running_mode=running,
                num_poses=4,
            )
        )
        self._hands = mp_vision.HandLandmarker.create_from_options(
            mp_vision.HandLandmarkerOptions(
                base_options=base("hand_landmarker.task"),
                running_mode=running,
                num_hands=4,
            )
        )
        self._face = mp_vision.FaceLandmarker.create_from_options(
            mp_vision.FaceLandmarkerOptions(
                base_options=base("face_landmarker.task"),
                running_mode=running,
                num_faces=4,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
            )
        )
        self._mp_vision = mp_vision

    def close(self) -> None:
        for obj in (self._pose, self._hands, self._face):
            closer = getattr(obj, "close", None)
            if closer:
                closer()

    def detect(
        self,
        frame_rgb: np.ndarray,
        timestamp_ms: int,
        frame_index: int,
        run_face_hands: Optional[bool] = None,
    ) -> tuple[list[PoseInstance], list[FaceInstance], list[HandInstance], bool]:
        import mediapipe as mp

        if run_face_hands is None:
            run_face_hands = should_run_face_hands(frame_index)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(frame_rgb))
        pose_result = self._pose.detect_for_video(image, timestamp_ms)
        poses = [_pose_instance(p, getattr(pose_result, "pose_landmarks", None), i) for i, p in enumerate(pose_result.pose_landmarks or [])]
        faces: list[FaceInstance] = []
        hands: list[HandInstance] = []
        if run_face_hands:
            face_result = self._face.detect_for_video(image, timestamp_ms)
            hand_result = self._hands.detect_for_video(image, timestamp_ms)
            faces = _faces(face_result, frame_rgb.shape[0])
            hands = _hands(hand_result)
        return poses, faces, hands, run_face_hands


def _lm_xyz(landmark: Any) -> tuple[float, float, float, float]:
    vis = float(getattr(landmark, "visibility", None) or getattr(landmark, "presence", 1.0) or 1.0)
    return float(landmark.x), float(landmark.y), float(getattr(landmark, "z", 0.0) or 0.0), vis


def _pose_instance(landmarks: Any, _all: Any, _i: int) -> PoseInstance:
    pts = [_lm_xyz(lm) for lm in landmarks]
    xyz = np.array([[p[0], p[1], p[2]] for p in pts], dtype=np.float64)
    vis = np.array([p[3] for p in pts], dtype=np.float64)
    return PoseInstance(xyz=xyz, vis=vis, bbox=bbox_from_landmarks(xyz[:, :2], vis))


def _faces(result: Any, frame_h: int) -> list[FaceInstance]:
    out: list[FaceInstance] = []
    lms = list(result.face_landmarks or [])
    matrices = list(result.facial_transformation_matrixes or [])
    blends = list(result.face_blendshapes or [])
    for i, landmarks in enumerate(lms):
        pts = [_lm_xyz(lm) for lm in landmarks]
        xyz = np.array([[p[0], p[1], p[2]] for p in pts], dtype=np.float64)
        vis = np.array([p[3] for p in pts], dtype=np.float64)
        bbox = bbox_from_landmarks(xyz[:, :2], vis)
        height_px = 0.0
        if bbox is not None:
            height_px = float((bbox[3] - bbox[1]) * frame_h)
        matrix = None
        if i < len(matrices):
            matrix = np.array(matrices[i], dtype=np.float64)
        bmap: dict[str, float] = {}
        if i < len(blends):
            for cat in blends[i]:
                name = getattr(cat, "category_name", None) or getattr(cat, "display_name", "")
                if name:
                    bmap[str(name)] = float(getattr(cat, "score", 0.0) or 0.0)
        out.append(
            FaceInstance(xyz=xyz, vis=vis, bbox=bbox, matrix=matrix, blendshapes=bmap, height_px=height_px)
        )
    return out


def _hands(result: Any) -> list[HandInstance]:
    out: list[HandInstance] = []
    lms = list(result.hand_landmarks or [])
    handed = list(result.handedness or [])
    for i, landmarks in enumerate(lms):
        pts = [_lm_xyz(lm) for lm in landmarks]
        xyz = np.array([[p[0], p[1], p[2]] for p in pts], dtype=np.float64)
        vis = np.array([p[3] for p in pts], dtype=np.float64)
        label = "unknown"
        if i < len(handed) and handed[i]:
            cat = handed[i][0]
            label = str(getattr(cat, "category_name", None) or getattr(cat, "display_name", "unknown"))
        out.append(
            HandInstance(
                xyz=xyz,
                vis=vis,
                handedness=label,
                bbox=bbox_from_landmarks(xyz[:, :2], vis),
            )
        )
    return out
