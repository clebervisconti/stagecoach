"""Landmark smoothing: One-Euro then Savitzky-Golay (SPEC §6.5, H)."""

from __future__ import annotations

from typing import Optional

import numpy as np
from scipy.signal import savgol_filter

from pipeline.vision.one_euro import OneEuroFilter

SG_WINDOW = 5
SG_POLY = 2


def savitzky_golay(series: np.ndarray, window: int = SG_WINDOW, poly: int = SG_POLY) -> np.ndarray:
    """Smooth along axis 0. Returns a copy; short series are unchanged."""
    n = series.shape[0]
    if n < window or window < poly + 2 or window % 2 == 0:
        return np.asarray(series, dtype=np.float64)
    return savgol_filter(series, window_length=window, polyorder=poly, axis=0, mode="interp")


class LandmarkSmoother:
    """One-Euro per landmark coordinate, then optional SG on the finished track."""

    def __init__(self, n_landmarks: int, n_coords: int = 3) -> None:
        self.filters = [
            [OneEuroFilter() for _ in range(n_coords)] for _ in range(n_landmarks)
        ]

    def step(self, t: float, xyz: np.ndarray) -> np.ndarray:
        out = np.array(xyz, dtype=np.float64, copy=True)
        for i, row in enumerate(out):
            for c, value in enumerate(row):
                if c >= len(self.filters[i]):
                    break
                out[i, c] = self.filters[i][c](t, float(value))
        return out


def smooth_track_xyz(
    times: np.ndarray,
    xyz: np.ndarray,
    vis: Optional[np.ndarray] = None,
) -> np.ndarray:
    """xyz shape (T, L, 3). One-Euro through time, then SG per coordinate."""
    t_count, n_land, n_coord = xyz.shape
    smoother = LandmarkSmoother(n_land, n_coord)
    one = np.zeros_like(xyz, dtype=np.float64)
    for i in range(t_count):
        one[i] = smoother.step(float(times[i]), xyz[i])
        if vis is not None:
            low = vis[i] < 0.3
            one[i, low] = xyz[i, low]
    return savitzky_golay(one)
