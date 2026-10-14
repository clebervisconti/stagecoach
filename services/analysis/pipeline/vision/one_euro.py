"""One-Euro filter (Casiez, Roussel, Vogel, CHI 2012) for landmark jitter.

Heuristic (H) per SPEC §6.5. Implemented from the paper's recurrence, not
copied from a third-party source.
"""

from __future__ import annotations

import math
from typing import Optional


def _alpha(dt: float, cutoff: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / max(dt, 1e-6))


class OneEuroFilter:
    """Adaptive low-pass filter for a scalar signal sampled at time t."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.007, d_cutoff: float = 1.0) -> None:
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x: Optional[float] = None
        self._dx = 0.0
        self._t: Optional[float] = None

    def reset(self) -> None:
        self._x = None
        self._dx = 0.0
        self._t = None

    def __call__(self, t: float, x: float) -> float:
        if self._x is None or self._t is None:
            self._x = x
            self._t = t
            self._dx = 0.0
            return x
        dt = max(t - self._t, 1e-6)
        dx = (x - self._x) / dt
        edx = _alpha(dt, self.d_cutoff) * dx + (1.0 - _alpha(dt, self.d_cutoff)) * self._dx
        cutoff = self.min_cutoff + self.beta * abs(edx)
        a = _alpha(dt, cutoff)
        xhat = a * x + (1.0 - a) * self._x
        self._x, self._dx, self._t = xhat, edx, t
        return xhat
