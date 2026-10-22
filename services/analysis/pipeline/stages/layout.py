"""Layout stage wrapper (spec §6.4)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pipeline.layout.detect import DETECTOR_VERSION, detect_layout
from pipeline.layout.faces import FaceDetector

STAGE_VERSION = "1.0.0"


@dataclass
class LayoutOutput:
    payload: dict[str, Any]
    artifacts: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"layout": self.payload, "artifacts": self.artifacts}


def run_layout_stage(
    *,
    video_path: Path,
    output_dir: Path,
    duration_s: float,
    frame_width: int,
    frame_height: int,
    delivery_mode: str = "webinar",
    detector: Optional[FaceDetector] = None,
    preview_source: Optional[Path] = None,
) -> LayoutOutput:
    payload = detect_layout(
        video_path,
        output_dir,
        duration_s=duration_s,
        frame_width=frame_width,
        frame_height=frame_height,
        delivery_mode=delivery_mode,
        detector=detector,
        preview_source=preview_source,
    )
    artifacts = {"layout": str(output_dir / "layout.json")}
    preview = output_dir / "layout_preview" / "segment_000.jpg"
    if preview.is_file():
        artifacts["layout_preview"] = str(preview)
    return LayoutOutput(payload=payload, artifacts=artifacts)


__all__ = ["DETECTOR_VERSION", "LayoutOutput", "STAGE_VERSION", "run_layout_stage"]
