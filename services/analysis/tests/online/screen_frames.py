"""Synthetic gray frames for screen-flow tests. Not a recording."""

from __future__ import annotations

import numpy as np

H = 360
W = 640


def static_frames(count: int) -> list[np.ndarray]:
    frame = np.full((H, W), 48, np.uint8)
    frame[40:140, 40:280] = 190
    frame[200:240, 300:500] = 90
    return [frame.copy() for _ in range(count)]


def pointer_frames(count: int) -> list[np.ndarray]:
    base = np.full((H, W), 36, np.uint8)
    base[20:300, 20:600] = 42
    frames = []
    for step in range(count):
        frame = base.copy()
        x = 40 + step * 12
        y = 80
        frame[y : y + 36, x : x + 36] = 250
        frames.append(frame)
    return frames


def scroll_frames(count: int, shift_px: int = 10) -> list[np.ndarray]:
    frames = []
    for step in range(count):
        frames.append(_scroll_frame(step * shift_px))
    return frames


def _scroll_frame(shift: int) -> np.ndarray:
    ys = (np.arange(H) + shift)[:, None]
    stripes = np.where(((ys // 20) % 2) == 0, 24, 230).astype(np.uint8)
    image = np.repeat(stripes, W, axis=1)
    column = ((np.arange(H) + shift) % 251).astype(np.uint8)
    image[:, 8:16] = column[:, None]
    return image


def typing_frames(count: int) -> list[np.ndarray]:
    rng = np.random.default_rng(4)
    base = np.full((H, W), 40, np.uint8)
    frames = []
    for step in range(count):
        frame = base.copy()
        width = min(W - 40, 160 + step * 40)
        frame[200:210, 20 : 20 + width] = rng.integers(0, 255, size=(10, width), dtype=np.uint8)
        frames.append(frame)
    return frames


def motion_frames(count: int) -> list[np.ndarray]:
    rng = np.random.default_rng(5)
    base = np.full((H, W), 28, np.uint8)
    frames = []
    for _ in range(count):
        frame = base.copy()
        frame[40:320, 200:360] = rng.integers(0, 255, size=(280, 160), dtype=np.uint8)
        frames.append(frame)
    return frames


def content_frames() -> list[np.ndarray]:
    rng = np.random.default_rng(6)
    first = rng.integers(0, 255, size=(H, W), dtype=np.uint8)
    second = rng.integers(0, 255, size=(H, W), dtype=np.uint8)
    return [first, second, second.copy(), second.copy()]


def slide_frame(kind: str) -> np.ndarray:
    image = np.zeros((H, W), np.uint8)
    if kind == "a":
        image[:, :220] = 230
    elif kind == "b":
        image[:, 420:] = 230
    else:
        image[::32, :] = 230
        image[:, ::32] = 230
    return image


def slide_sequence() -> list[np.ndarray]:
    frames = []
    for kind, count in (("a", 5), ("b", 5), ("c", 5)):
        frame = slide_frame(kind)
        frames.extend(frame.copy() for _ in range(count))
    return frames
