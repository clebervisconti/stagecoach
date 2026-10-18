"""Vision stage: MediaPipe pose/hands/face on CPU (issue #38, SPEC §6.5).

Stores per-second aggregates, not frames. Raw landmarks are discarded unless
keep_detailed_tracking. Expression blendshape aggregates require
expression_analysis. OpenFace is not used. No emotion labels.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from pipeline.consent import VisionDecision
from pipeline.vision.aggregate import aggregate_face, aggregate_pose, write_encrypted_parquet
from pipeline.vision.crypto import resolve_artifact_key, write_encrypted_json
from pipeline.vision.features import (
    FACE_HANDS_FPS,
    POSE_FPS,
    FrameDetections,
    pose_frame_features,
    rotation_to_ypr,
    should_run_face_hands,
)
from pipeline.vision.models import MODEL_REGISTRY
from pipeline.vision.smoothing import smooth_track_xyz
from pipeline.vision.tracking import PrimaryTracker, bbox_from_landmarks

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"


@dataclass
class VisionOutput:
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "stage_version": STAGE_VERSION,
        }


def _assert_no_openface() -> None:
    import sys

    for name in list(sys.modules):
        if "openface" in name.lower():
            raise RuntimeError("OpenFace must not be imported in the product")


def _select_primary(frame: FrameDetections, tracker: PrimaryTracker) -> Optional[int]:
    boxes = []
    index_map = []
    for i, pose in enumerate(frame.poses):
        box = pose.bbox if pose.bbox is not None else bbox_from_landmarks(pose.xyz[:, :2], pose.vis)
        pose.bbox = box
        if box is None:
            continue
        boxes.append(box)
        index_map.append(i)
    if not boxes:
        return None
    ids = tracker.update(boxes, frame.frame_index)
    primary = tracker.primary_id
    if primary is None:
        return None
    for j, tid in enumerate(ids):
        if tid == primary:
            return index_map[j]
    return index_map[0]


def _match_face_hand(instances, pose_bbox):
    if not instances or pose_bbox is None:
        return None
    pcx = 0.5 * (pose_bbox[0] + pose_bbox[2])
    pcy = 0.5 * (pose_bbox[1] + pose_bbox[3])
    best_i, best_d = None, 1e9
    for i, inst in enumerate(instances):
        box = inst.bbox
        if box is None:
            continue
        cx = 0.5 * (box[0] + box[2])
        cy = 0.5 * (box[1] + box[3])
        d = (cx - pcx) ** 2 + (cy - pcy) ** 2
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def run_vision_stage(
    *,
    output_dir: Path,
    session_id: str,
    decision: VisionDecision,
    video_path: Optional[Path] = None,
    frames: Optional[list[FrameDetections]] = None,
    encryption_key: Optional[bytes] = None,
    models_dir: Optional[Path] = None,
    camera_setup: str = "unknown",
) -> VisionOutput:
    """Run pose every frame and face/hands at 10 fps when video_analysis is granted."""
    _assert_no_openface()
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if not decision.run_pose:
        return VisionOutput(skipped=True, skip_reason=decision.skip_reason or "consent_denied:video_analysis")

    key = resolve_artifact_key(encryption_key)

    if frames is None:
        if video_path is None or not Path(video_path).exists():
            return VisionOutput(skipped=True, skip_reason="no_video_stream")
        from pipeline.vision import mediapipe_cpu

        if not mediapipe_cpu.mediapipe_available():
            return VisionOutput(skipped=True, skip_reason="mediapipe_unavailable")
        frames = list(_detect_video(Path(video_path), decision, models_dir=models_dir))

    tracker = PrimaryTracker()
    pose_rows: list[dict[str, Any]] = []
    face_rows: list[dict[str, Any]] = []
    raw_pose: list[np.ndarray] = []
    raw_pose_t: list[float] = []
    raw_pose_vis: list[np.ndarray] = []
    prev_xyz: Optional[np.ndarray] = None
    prev_t: Optional[float] = None
    pose_on_frames = 0
    face_on_frames = 0
    hand_on_frames = 0

    primary_xyz: list[np.ndarray] = []
    primary_t: list[float] = []
    primary_vis: list[np.ndarray] = []
    primary_meta: list[FrameDetections] = []
    primary_pose: list[Any] = []

    for frame in frames:
        pose_on_frames += 1
        idx = _select_primary(frame, tracker)
        if idx is None:
            pose_rows.append({"t": frame.t, "person_visible": 0.0})
            continue
        pose = frame.poses[idx]
        primary_xyz.append(pose.xyz)
        primary_t.append(frame.t)
        primary_vis.append(pose.vis)
        primary_meta.append(frame)
        primary_pose.append(pose)

    if primary_xyz:
        stacked = np.stack(primary_xyz, axis=0)
        times = np.asarray(primary_t, dtype=np.float64)
        vis_stack = np.stack(primary_vis, axis=0)
        smoothed = smooth_track_xyz(times, stacked, vis_stack)
        for i, pose in enumerate(primary_pose):
            pose.xyz = smoothed[i]
            rebuilt = bbox_from_landmarks(pose.xyz[:, :2], pose.vis)
            if rebuilt is not None:
                pose.bbox = rebuilt

    for i, pose in enumerate(primary_pose):
        frame = primary_meta[i]
        dt = (frame.t - prev_t) if prev_t is not None else 0.0
        feats = pose_frame_features(pose, prev_xyz, dt if dt > 0 else 1.0 / POSE_FPS)
        feats["t"] = frame.t
        pose_rows.append(feats)
        if decision.keep_raw_landmarks:
            raw_pose.append(pose.xyz.copy())
            raw_pose_t.append(frame.t)
            raw_pose_vis.append(pose.vis.copy())
        if frame.run_face_hands:
            pbox = pose.bbox
            fi = _match_face_hand(frame.faces, pbox)
            if fi is not None:
                face_on_frames += 1
                face = frame.faces[fi]
                yaw = pitch = roll = float("nan")
                if face.matrix is not None:
                    yaw, pitch, roll = rotation_to_ypr(face.matrix)
                face_rows.append(
                    {
                        "t": frame.t,
                        "face_visible": 1.0,
                        "face_height_px": face.height_px,
                        "yaw_deg": yaw,
                        "pitch_deg": pitch,
                        "roll_deg": roll,
                        "blendshapes": _stored_blendshapes(face.blendshapes, decision),
                    }
                )
            else:
                face_rows.append({"t": frame.t, "face_visible": 0.0, "face_height_px": 0.0})
            if frame.hands:
                hand_on_frames += 1
        prev_xyz = pose.xyz
        prev_t = frame.t

    pose_rows.sort(key=lambda row: float(row.get("t") or 0.0))
    face_rows.sort(key=lambda row: float(row.get("t") or 0.0))

    pose_cols = aggregate_pose(pose_rows)
    face_cols = aggregate_face(face_rows, include_blendshapes=decision.run_expression_metrics)
    pose_path = dest / "pose.parquet"
    face_path = dest / "face.parquet"
    write_encrypted_parquet(pose_path, pose_cols, key)
    write_encrypted_parquet(face_path, face_cols, key)

    artifacts = {"pose": str(pose_path), "face": str(face_path)}
    raw_path = dest / "landmarks.parquet"
    if decision.keep_raw_landmarks and raw_pose:
        raw_cols = _raw_columns(raw_pose_t, raw_pose, raw_pose_vis)
        write_encrypted_parquet(raw_path, raw_cols, key)
        artifacts["landmarks"] = str(raw_path)
    elif raw_path.exists():
        raw_path.unlink()

    # Never persist RGB frames as vision features.
    for leftover in dest.glob("vision_frame_*.png"):
        leftover.unlink()

    n_seconds = int(pose_cols["t_s"].size) if pose_cols else 0
    person_ratio = (
        float(np.nanmean(pose_cols["person_visible_ratio"])) if n_seconds else 0.0
    )
    from pipeline.vision.events import detect_events
    from pipeline.vision.quality import build_quality

    frame_h = frames[0].height if frames else 480
    quality = build_quality(
        pose_rows,
        face_rows,
        frames or [],
        declared_setup=camera_setup,
        has_video=True,
        frame_height=frame_h,
    )
    scale = float((quality.get("camera_setup") or {}).get("threshold_scale") or 1.0)
    events = detect_events(
        pose_rows,
        face_rows,
        expression_metrics=decision.run_expression_metrics,
        threshold_scale=scale,
    )
    events_payload = {
        "version": STAGE_VERSION,
        "emotion_inference": False,
        "events": events,
        "threshold_scale": scale,
    }
    quality_path = dest / "vision_quality.json"
    events_path = dest / "vision_events.json"
    quality_path.write_text(json.dumps(quality, indent=2) + "\n", encoding="utf-8")
    events_path.write_text(json.dumps(events_payload, indent=2) + "\n", encoding="utf-8")
    artifacts["vision_quality"] = str(quality_path)
    artifacts["vision_events"] = str(events_path)
    from pipeline.accessibility import load_accessibility
    from pipeline.vision.gestures import compute_gesture_metrics

    duration = float(frames[-1].t) if frames else 0.0
    webcam = (quality.get("camera_setup") or {}).get("detected") == "to_camera"
    gesture = compute_gesture_metrics(
        pose_rows,
        events,
        duration_s=max(duration, 1.0),
        accessibility=load_accessibility(dest),
        webcam_framing=bool(webcam),
        audio_only=False,
        fps=POSE_FPS,
    )
    gesture_path = dest / "gesture_metrics.json"
    if gesture is not None:
        gesture_path.write_text(json.dumps(gesture, indent=2) + "\n", encoding="utf-8")
        artifacts["gesture_metrics"] = str(gesture_path)
    elif gesture_path.exists():
        gesture_path.unlink()

    from pipeline.vision.gaze import compute_gaze_metrics

    gaze_path = dest / "gaze_metrics.json"
    if decision.run_face_landmarks:
        detected = (quality.get("camera_setup") or {}).get("detected") or camera_setup
        declared = (quality.get("camera_setup") or {}).get("declared") or camera_setup
        gaze_setup = declared if declared in {"stage", "to_camera"} else detected
        gaze = compute_gaze_metrics(
            face_rows,
            duration_s=max(duration, 1.0),
            setup=str(gaze_setup or "unknown"),
            accessibility=load_accessibility(dest),
            audio_only=False,
            mean_face_height_px=quality.get("mean_face_height_px"),
        )
        if gaze is not None:
            gaze_path.write_text(json.dumps(gaze, indent=2) + "\n", encoding="utf-8")
            artifacts["gaze_metrics"] = str(gaze_path)
        elif gaze_path.exists():
            gaze_path.unlink()
    elif gaze_path.exists():
        gaze_path.unlink()

    expr_path = dest / "expression_metrics.json"
    if decision.run_expression_metrics:
        from pipeline.vision.expressiveness import compute_expression_metrics

        expr = compute_expression_metrics(face_rows, events, duration_s=max(duration, 1.0))
        if expr is not None:
            write_encrypted_json(expr_path, expr, key)
            artifacts["expression_metrics"] = str(expr_path)
    elif expr_path.exists():
        expr_path.unlink()

    metrics = {
        "cpu_only": True,
        "openface_used": False,
        "emotion_inference": False,
        "pose_fps": POSE_FPS,
        "face_hands_fps": FACE_HANDS_FPS,
        "pose_frames": pose_on_frames,
        "face_frames": face_on_frames,
        "hand_frames": hand_on_frames,
        "person_visible_ratio": person_ratio,
        "keep_raw_landmarks": bool(decision.keep_raw_landmarks),
        "expression_metrics": bool(decision.run_expression_metrics),
        "models": [
            {"model_name": m["model_name"], "version": m["version"], "license": m["license"], "sha256": m["sha256"]}
            for m in MODEL_REGISTRY
        ],
        "session_id": session_id,
        "stage_version": STAGE_VERSION,
        "event_count": len(events),
        "camera_setup": quality.get("camera_setup"),
    }
    metrics_path = dest / "vision_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    artifacts["vision_metrics"] = str(metrics_path)

    logger.info("vision stage wrote pose/face aggregates session=%s", session_id)
    return VisionOutput(artifacts=artifacts, metrics=metrics)


def _stored_blendshapes(blendshapes: dict[str, float], decision: VisionDecision) -> dict[str, float]:
    """Keep eyeLook* for gaze; expression subset only with expression_analysis.

    Numeric scores only. No emotion labels.
    """
    if decision.run_expression_metrics:
        return dict(blendshapes)
    return {k: v for k, v in blendshapes.items() if k.startswith("eyeLook")}


def _raw_columns(times: list[float], xyzs: list[np.ndarray], vis: list[np.ndarray]) -> dict[str, np.ndarray]:
    t_out: list[float] = []
    idx_out: list[float] = []
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    vs: list[float] = []
    for t, xyz, v in zip(times, xyzs, vis):
        for i in range(xyz.shape[0]):
            t_out.append(t)
            idx_out.append(float(i))
            xs.append(float(xyz[i, 0]))
            ys.append(float(xyz[i, 1]))
            zs.append(float(xyz[i, 2]))
            vs.append(float(v[i]))
    return {
        "t": np.asarray(t_out),
        "landmark_index": np.asarray(idx_out),
        "x": np.asarray(xs),
        "y": np.asarray(ys),
        "z": np.asarray(zs),
        "visibility": np.asarray(vs),
        "kind": np.array(["pose"] * len(t_out)),
    }


def _detect_video(
    video_path: Path,
    decision: VisionDecision,
    models_dir: Optional[Path] = None,
) -> list[FrameDetections]:
    from pipeline.vision.decode import iter_rgb_frames, video_size
    from pipeline.vision.mediapipe_cpu import CpuLandmarkers

    width, height, fps = video_size(video_path)
    detector = CpuLandmarkers(models_dir=models_dir)
    out: list[FrameDetections] = []
    prev_gray: Optional[np.ndarray] = None
    try:
        for index, t, frame in iter_rgb_frames(video_path):
            run_fh = should_run_face_hands(index, fps or POSE_FPS) and (
                decision.run_face_landmarks or decision.run_hands
            )
            ts_ms = int(round(t * 1000.0))
            poses, faces, hands, ran = detector.detect(
                frame, ts_ms, index, run_face_hands=run_fh
            )
            if not decision.run_face_landmarks:
                faces = []
            if not decision.run_hands:
                hands = []
            gray = frame.mean(axis=2)
            luma = float(gray.mean() / 255.0)
            motion = 0.0
            if prev_gray is not None:
                motion = float(np.mean(np.abs(gray - prev_gray)) / 255.0)
            prev_gray = gray
            out.append(
                FrameDetections(
                    t=t,
                    frame_index=index,
                    width=width,
                    height=height,
                    poses=poses,
                    faces=faces,
                    hands=hands,
                    run_face_hands=ran,
                    luma=luma,
                    motion=motion,
                )
            )
            del frame
    finally:
        detector.close()
    return out
