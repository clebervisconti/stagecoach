"""prepare_session: ingest + single-layout detection (spec §6.4)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Optional

from pipeline.layout.faces import FaceDetector
from pipeline.layout.review import needs_layout_review
from pipeline.stages.ingest import ingest
from pipeline.stages.layout import run_layout_stage

logger = logging.getLogger(__name__)

INGEST_JSON = "ingest.json"


def write_ingest_json(output_dir: Path, payload: dict[str, Any]) -> Path:
    dest = output_dir / INGEST_JSON
    dest.write_text(json.dumps(payload, indent=2) + "\n")
    return dest


def load_ingest_json(output_dir: Path) -> dict[str, Any]:
    dest = output_dir / INGEST_JSON
    if not dest.is_file():
        raise FileNotFoundError(f"ingest.json missing in {output_dir}")
    return json.loads(dest.read_text())


def prepare_session(
    *,
    input_path: Path,
    output_dir: Path,
    session_id: str,
    delivery_mode: str = "webinar",
    detector: Optional[FaceDetector] = None,
    video_analysis_consent: bool = True,
    layout_review_pref: str = "when_unsure",
    confirmed_layout_count: int = 0,
    on_progress: Optional[Callable[..., Any]] = None,
    on_media: Optional[Callable[..., Any]] = None,
) -> dict[str, Any]:
    """Run ingest then layout. Pure enough for tests (no DB, no enqueue)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ingest_result = ingest(
        input_path,
        output_dir,
        session_id,
        on_progress=on_progress,
        on_media=on_media,
    )
    ingest_dict = ingest_result.to_dict()
    write_ingest_json(output_dir, ingest_dict)
    modality = ingest_dict.get("modality") or {}
    media = ingest_dict.get("media_info") or {}
    audio_only = bool(modality.get("is_audio_only")) or not media.get("has_video")

    if audio_only:
        return {
            "ingest": ingest_dict,
            "layout": None,
            "status": "processing",
            "skip_layout": True,
            "audio_only": True,
            "auto_confirmed": False,
            "reason": "audio_only_media",
        }

    if not video_analysis_consent:
        return {
            "ingest": ingest_dict,
            "layout": None,
            "status": "processing",
            "skip_layout": True,
            "audio_only": True,
            "auto_confirmed": False,
            "reason": "consent_video_off",
        }

    analysis = Path(ingest_dict["artifacts"].get("analysis") or output_dir / "analysis.mp4")
    source = analysis if analysis.is_file() else input_path
    layout_out = run_layout_stage(
        video_path=source,
        output_dir=output_dir,
        duration_s=float(media.get("duration") or 0),
        frame_width=int(media.get("width") or 1920),
        frame_height=int(media.get("height") or 1080),
        delivery_mode=delivery_mode,
        detector=detector,
        preview_source=input_path if input_path.is_file() else source,
    )
    layout = layout_out.payload
    review = needs_layout_review(
        pref=layout_review_pref,
        confirmed_count=confirmed_layout_count,
        confidence=float(layout.get("confidence") or 0),
        segment_confidences=[float(seg.get("confidence") or 0) for seg in layout.get("segments") or []],
        review_reason=layout.get("review_reason"),
        n_segments=len(layout.get("segments") or []),
    )
    if review:
        return {
            "ingest": ingest_dict,
            "layout": layout,
            "status": "layout_review",
            "skip_layout": False,
            "audio_only": False,
            "auto_confirmed": False,
            "reason": layout.get("review_reason"),
        }
    layout["status"] = "auto_confirmed"
    (output_dir / "layout.json").write_text(json.dumps(layout, indent=2) + "\n")
    return {
        "ingest": ingest_dict,
        "layout": layout,
        "status": "processing",
        "skip_layout": False,
        "audio_only": False,
        "auto_confirmed": True,
        "reason": None,
    }


EnqueueFn = Callable[..., Any]
