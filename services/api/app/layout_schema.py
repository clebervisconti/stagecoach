"""Validated layout edits (spec §8.4). Coordinates stay unitless 0–1."""

from __future__ import annotations

import math
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.routers.sessions import AnalysisWindow

MIN_REGION = 0.05
COVERAGE_TOLERANCE_S = 0.25
EDGE_TOLERANCE = 1e-3


class LayoutRegionIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1, max_length=64)
    role: Literal["camera", "screen", "other_participant", "ignore"]
    x: float
    y: float
    w: float
    h: float
    confidence: Optional[float] = None
    source: Literal["auto", "user"] = "user"

    @model_validator(mode="after")
    def _inside_frame(self) -> "LayoutRegionIn":
        for name, value in (("x", self.x), ("y", self.y), ("w", self.w), ("h", self.h)):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        if self.w < MIN_REGION or self.h < MIN_REGION:
            raise ValueError("region must cover at least 5% of the frame")
        if (
            self.x < -EDGE_TOLERANCE
            or self.y < -EDGE_TOLERANCE
            or self.x + self.w > 1 + EDGE_TOLERANCE
            or self.y + self.h > 1 + EDGE_TOLERANCE
        ):
            raise ValueError("region must stay inside the frame")
        return self


class LayoutSegmentIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    index: int = Field(ge=0)
    t_start: float
    t_end: float
    kind: str = "composite"
    confidence: float = 1
    regions: list[LayoutRegionIn] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _span_and_roles(self) -> "LayoutSegmentIn":
        if not math.isfinite(self.t_start) or not math.isfinite(self.t_end):
            raise ValueError("segment times must be finite")
        if self.t_end <= self.t_start:
            raise ValueError("segment t_end must be greater than t_start")
        cameras = sum(region.role == "camera" for region in self.regions)
        screens = sum(region.role == "screen" for region in self.regions)
        if cameras > 1 or screens > 1:
            raise ValueError("at most one camera and one screen per segment")
        return self


class LayoutPutBody(BaseModel):
    version: int = Field(ge=1)
    segments: list[LayoutSegmentIn] = Field(min_length=1, max_length=200)
    analysis_window: Optional[AnalysisWindow] = None


def validate_timeline(segments: list[LayoutSegmentIn], duration_s: float) -> None:
    """Segments are contiguous, non-overlapping, and cover the recording."""
    ordered = sorted(segments, key=lambda segment: (segment.t_start, segment.index))
    if abs(ordered[0].t_start) > COVERAGE_TOLERANCE_S:
        raise ValueError("segments must start at the beginning of the recording")
    if duration_s > 0 and abs(ordered[-1].t_end - duration_s) > COVERAGE_TOLERANCE_S:
        raise ValueError("segments must cover the recording")
    for prev, nxt in zip(ordered, ordered[1:]):
        if nxt.t_start < prev.t_end - 0.05:
            raise ValueError("segments overlap")
        if nxt.t_start - prev.t_end > COVERAGE_TOLERANCE_S:
            raise ValueError("segments must be contiguous")


def validate_window_inside(window: Optional[AnalysisWindow], duration_s: float) -> None:
    if window is None or duration_s <= 0:
        return
    if window.start_s < -EDGE_TOLERANCE or window.end_s > duration_s + COVERAGE_TOLERANCE_S:
        raise ValueError("analysis window must sit inside the recording")


def windows_equal(left: Any, right: Any, tolerance: float = 0.05) -> bool:
    if not left and not right:
        return True
    if not left or not right:
        return False
    return abs(float(left["start_s"]) - float(right["start_s"])) <= tolerance and abs(
        float(left["end_s"]) - float(right["end_s"])
    ) <= tolerance


def _region_signature(region: Any) -> tuple:
    if isinstance(region, LayoutRegionIn):
        role, x, y, w, h = region.role, region.x, region.y, region.w, region.h
    else:
        role, x, y, w, h = region["role"], region["x"], region["y"], region["w"], region["h"]
    return (role, round(float(x), 4), round(float(y), 4), round(float(w), 4), round(float(h), 4))


def count_edits(detected: dict[str, Any], body: LayoutPutBody) -> int:
    """How many structural changes the user made against the detected layout."""
    before_segments = list(detected.get("segments") or [])
    edits = 0
    if len(before_segments) != len(body.segments):
        edits += 1
    for index, segment in enumerate(body.segments):
        before = before_segments[index] if index < len(before_segments) else None
        if before is None:
            edits += 1
            continue
        if abs(float(before.get("t_start") or 0) - segment.t_start) > 0.05 or abs(
            float(before.get("t_end") or 0) - segment.t_end
        ) > 0.05:
            edits += 1
        before_regions = sorted(_region_signature(region) for region in (before.get("regions") or []))
        after_regions = sorted(_region_signature(region) for region in segment.regions)
        if before_regions != after_regions:
            edits += 1
    window = body.analysis_window.model_dump() if body.analysis_window else None
    if not windows_equal(detected.get("analysis_window"), window):
        edits += 1
    return edits


def confirmed_document(detected: dict[str, Any], body: LayoutPutBody, *, version: int, status: str) -> dict[str, Any]:
    document = dict(detected)
    document["version"] = version
    document["status"] = status
    document["analysis_window"] = body.analysis_window.model_dump() if body.analysis_window else None
    document["segments"] = []
    for index, segment in enumerate(sorted(body.segments, key=lambda row: (row.t_start, row.index))):
        dumped = segment.model_dump()
        dumped["index"] = index
        document["segments"].append(dumped)
    return document


def reanalyse_seed(payload: dict[str, Any]) -> dict[str, Any]:
    """Layout document for a new job. Version restarts so the editor can lock it."""
    document = dict(payload)
    document["status"] = "detected"
    document["version"] = 1
    return document
