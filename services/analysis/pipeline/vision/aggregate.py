"""Per-second pose.parquet / face.parquet writers (SPEC §6.5 step 4)."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pipeline.vision.crypto import encrypt_bytes
from pipeline.vision.features import BLENDSHAPE_SUBSET, EYE_LOOK

POSE_COLUMNS = (
    "t_s",
    "n_frames",
    "person_visible_ratio",
    "shoulder_width_mean",
    "wrist_l_x",
    "wrist_l_y",
    "wrist_r_x",
    "wrist_r_y",
    "wrist_speed_l",
    "wrist_speed_r",
    "hand_face_dist",
    "hip_mid_x",
    "hip_mid_y",
    "bbox_cx",
    "bbox_cy",
    "bbox_w",
    "bbox_h",
    "visibility_mean",
    "wrist_l_vis",
    "wrist_r_vis",
)

FACE_BASE_COLUMNS = (
    "t_s",
    "n_frames",
    "face_visible_ratio",
    "face_height_px",
    "yaw_deg",
    "pitch_deg",
    "roll_deg",
)


def _nanmean(values: list[float]) -> float:
    arr = np.asarray(values, dtype=np.float64)
    if arr.size == 0 or np.all(np.isnan(arr)):
        return float("nan")
    return float(np.nanmean(arr))


def bucket_seconds(rows: Iterable[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    buckets: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        sec = int(math_floor(float(row["t"])))
        buckets.setdefault(sec, []).append(row)
    return buckets


def math_floor(x: float) -> int:
    return int(np.floor(x))


def aggregate_pose(rows: list[dict[str, Any]]) -> dict[str, np.ndarray]:
    buckets = bucket_seconds(rows)
    seconds = sorted(buckets)
    cols: dict[str, list[float]] = {name: [] for name in POSE_COLUMNS}
    for sec in seconds:
        group = buckets[sec]
        n = len(group)
        vis = [1.0 if g.get("person_visible") else 0.0 for g in group]
        cols["t_s"].append(float(sec))
        cols["n_frames"].append(float(n))
        cols["person_visible_ratio"].append(float(np.mean(vis)) if vis else 0.0)
        for key in POSE_COLUMNS:
            if key in {"t_s", "n_frames", "person_visible_ratio"}:
                continue
            cols[key].append(_nanmean([float(g.get(key, float("nan"))) for g in group]))
    return {k: np.asarray(v, dtype=np.float64) for k, v in cols.items()}


def aggregate_face(
    rows: list[dict[str, Any]],
    *,
    include_blendshapes: bool,
) -> dict[str, np.ndarray]:
    buckets = bucket_seconds(rows)
    seconds = sorted(buckets)
    names = list(FACE_BASE_COLUMNS) + list(EYE_LOOK)
    if include_blendshapes:
        names.extend(BLENDSHAPE_SUBSET)
    cols: dict[str, list[float]] = {name: [] for name in names}
    for sec in seconds:
        group = buckets[sec]
        n = len(group)
        vis = [1.0 if g.get("face_visible") else 0.0 for g in group]
        cols["t_s"].append(float(sec))
        cols["n_frames"].append(float(n))
        cols["face_visible_ratio"].append(float(np.mean(vis)) if vis else 0.0)
        cols["face_height_px"].append(_nanmean([float(g.get("face_height_px", float("nan"))) for g in group]))
        cols["yaw_deg"].append(_nanmean([float(g.get("yaw_deg", float("nan"))) for g in group]))
        cols["pitch_deg"].append(_nanmean([float(g.get("pitch_deg", float("nan"))) for g in group]))
        cols["roll_deg"].append(_nanmean([float(g.get("roll_deg", float("nan"))) for g in group]))
        for key in EYE_LOOK:
            cols[key].append(_nanmean([float((g.get("blendshapes") or {}).get(key, float("nan"))) for g in group]))
        if include_blendshapes:
            for key in BLENDSHAPE_SUBSET:
                cols[key].append(
                    _nanmean([float((g.get("blendshapes") or {}).get(key, float("nan"))) for g in group])
                )
    return {k: np.asarray(v, dtype=np.float64) for k, v in cols.items()}


def write_encrypted_parquet(path: Path, columns: dict[str, np.ndarray], key: bytes) -> None:
    arrays = {name: np.asarray(values) for name, values in columns.items()}
    table = pa.table(arrays)
    buf = io.BytesIO()
    pq.write_table(table, buf)
    path.write_bytes(encrypt_bytes(buf.getvalue(), key))


def read_encrypted_parquet(path: Path, key: bytes):
    from pipeline.vision.crypto import decrypt_bytes

    raw = decrypt_bytes(path.read_bytes(), key)
    return pq.read_table(pa.BufferReader(raw))
