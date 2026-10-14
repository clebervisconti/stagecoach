"""Slides stage (issue #43, SPEC §6.6 steps 1–6). CPU only. No emotion inference."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from pipeline.slides.antivirus import DeckRejected, scan_deck_file
from pipeline.slides.deck import extract_deck
from pipeline.slides.keyframes import extract_keyframe
from pipeline.slides.match import match_slide, reading_overlap
from pipeline.slides.ocr import ocr_image
from pipeline.slides.region import detect_slide_region, full_frame_region
from pipeline.slides.scenes import detect_scenes, merge_short_scenes

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"


@dataclass
class SlidesOutput:
    artifacts: dict[str, str]
    metrics: dict[str, Any]
    skipped: bool
    skip_reason: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifacts": self.artifacts,
            "metrics": self.metrics,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "version": STAGE_VERSION,
        }


def find_deck_path(output_dir: Path, explicit: Optional[Path] = None) -> Optional[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    for folder in (output_dir, output_dir.parent):
        for name in ("deck.pptx", "deck.pdf"):
            candidates.append(folder / name)
    for path in candidates:
        if path.is_file():
            return path
    return None


def _sample_frames(video_path: Path, max_frames: int = 8):
    try:
        import cv2
    except ImportError:
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    duration = (total / fps) if fps else 0.0
    frames = []
    if total <= 0:
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
        cap.release()
        return frames
    indexes = [int(i * max(total - 1, 0) / max(max_frames - 1, 1)) for i in range(max_frames)]
    for idx in indexes:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    cap.release()
    return frames


def _video_meta(video_path: Path) -> tuple[int, int, float]:
    try:
        import cv2
    except ImportError:
        return 1, 1, 0.0
    cap = cv2.VideoCapture(str(video_path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1)
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
    cap.release()
    duration = (n / fps) if fps else 0.0
    return w, h, duration


def _spoken(transcript: Optional[dict[str, Any]], start: float, end: float) -> str:
    if not transcript:
        return ""
    parts = []
    for seg in transcript.get("segments") or []:
        s = float(seg.get("start") or 0.0)
        e = float(seg.get("end") or 0.0)
        if e < start or s > end:
            continue
        parts.append(str(seg.get("text") or ""))
    return " ".join(parts)


def _ingest_flags(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "ingest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run_slides_stage(
    *,
    output_dir: Path,
    session_id: str,
    video_path: Optional[Path] = None,
    deck_path: Optional[Path] = None,
    camera_setup: str = "unknown",
    language: str = "en",
    transcript: Optional[dict[str, Any]] = None,
    is_screen_recording: Optional[bool] = None,
    is_audio_only: bool = False,
    llm_client: Any = None,
) -> SlidesOutput:
    """Write slides.json / deck_text.json / keyframes. Missing inputs stay empty, never scored."""
    dest = Path(output_dir)
    dest.mkdir(parents=True, exist_ok=True)
    keyframe_dir = dest / "keyframes"
    artifacts: dict[str, str] = {}
    deck_file = find_deck_path(dest, deck_path)
    deck_payload = None
    deck_error = None
    if deck_file is not None:
        try:
            scan_deck_file(deck_file)
            deck_payload = extract_deck(deck_file)
        except DeckRejected as exc:
            deck_error = str(exc)
            logger.info("deck rejected session=%s reason=%s", session_id, type(exc).__name__)
        except Exception as exc:
            deck_error = type(exc).__name__
            logger.info("deck extract failed session=%s", session_id)

    if deck_payload:
        deck_text_path = dest / "deck_text.json"
        deck_text_path.write_text(json.dumps(deck_payload, indent=2) + "\n", encoding="utf-8")
        artifacts["deck_text"] = str(deck_text_path)

    video = Path(video_path) if video_path else dest / "analysis.mp4"
    has_video = video.is_file() and not is_audio_only
    if is_screen_recording is None:
        ingest = _ingest_flags(dest)
        is_screen_recording = bool((ingest.get("modality") or {}).get("is_screen_recording"))
        if camera_setup == "screen_recording":
            is_screen_recording = True

    slides: list[dict[str, Any]] = []
    region = full_frame_region(1, 1)
    engine = None
    if has_video:
        width, height, duration = _video_meta(video)
        frames = _sample_frames(video)
        region = detect_slide_region(
            frames,
            setup=camera_setup,
            is_screen_recording=bool(is_screen_recording),
        )
        if region.get("w", 0) <= 1:
            region = {**full_frame_region(width, height), "method": region.get("method") or "full_frame"}
        detected = detect_scenes(video, crop=region, duration_s=duration)
        engine = detected["engine"]
        scenes = detected["scenes"] or [(0.0, max(duration, 0.1))]
        scenes = merge_short_scenes(scenes)
        keyframe_dir.mkdir(parents=True, exist_ok=True)
        pages = (deck_payload or {}).get("pages") or []
        for i, (start, end) in enumerate(scenes, start=1):
            kf = extract_keyframe(
                video,
                start,
                end,
                keyframe_dir / f"slide_{i:03d}.jpg",
                region=region,
            )
            ocr = ocr_image(Path(kf["path"]) if kf.get("path") else keyframe_dir / "missing.jpg", language=language)
            text = ocr.get("text") or ""
            if pages:
                matched = match_slide(text, pages)
                if matched.get("deck_page"):
                    page = next((p for p in pages if p.get("index") == matched["deck_page"]), None)
                    if page and (page.get("word_count") or 0) >= (len(text.split()) if text else 0):
                        text = page.get("text") or text
            else:
                matched = {"deck_page": None, "score": None, "method": None}
            spoken = _spoken(transcript, start, end)
            overlap = reading_overlap(text, spoken) if text and spoken else None
            lines = [ln for ln in (text or "").splitlines() if ln.strip()]
            title = lines[0] if lines else ""
            slides.append(
                {
                    "index": i,
                    "t_start": round(float(start), 3),
                    "t_end": round(float(end), 3),
                    "dwell_s": round(float(end - start), 3),
                    "keyframe": kf.get("path"),
                    "keyframe_t": kf.get("t"),
                    "sharpness": kf.get("sharpness"),
                    "text": text,
                    "title": title,
                    "word_count": len(text.split()) if text else 0,
                    "bullet_count": sum(
                        1 for ln in lines[1:] if ln.lstrip()[:1] in {"•", "-", "*", "·"}
                    ),
                    "ocr_engine": ocr.get("engine"),
                    "deck_page": matched.get("deck_page"),
                    "match_method": matched.get("method"),
                    "match_score": matched.get("score"),
                    "reading_overlap": overlap,
                    "region": {k: region.get(k) for k in ("x", "y", "w", "h")},
                }
            )
    elif deck_payload:
        # Deck only: no visible screen. Alignment happens in category 8 (#44).
        for page in deck_payload.get("pages") or []:
            slides.append(
                {
                    "index": int(page.get("index") or 0),
                    "t_start": None,
                    "t_end": None,
                    "dwell_s": None,
                    "keyframe": None,
                    "text": page.get("text") or "",
                    "title": page.get("title") or "",
                    "word_count": page.get("word_count") or 0,
                    "bullet_count": page.get("bullet_count") or 0,
                    "ocr_engine": None,
                    "deck_page": page.get("index"),
                    "match_method": "deck_only",
                    "match_score": 1.0,
                    "reading_overlap": None,
                    "region": None,
                }
            )

    skipped = not slides
    reason = None
    if skipped:
        if deck_error:
            reason = f"Deck rejected or unreadable: {deck_error}"
        elif is_audio_only and not deck_payload:
            reason = "Audio-only media has no slide region and no deck was uploaded."
        else:
            reason = "No slides were detected and no deck was uploaded."

    payload = {
        "version": STAGE_VERSION,
        "session_id": session_id,
        "cpu_only": True,
        "paddleocr": False,
        "pyscenedetect": engine == "pyscenedetect" if engine else False,
        "scene_engine": engine,
        "region": region,
        "camera_setup": camera_setup,
        "deck_error": deck_error,
        "slides": slides,
        "slide_count": len(slides),
        "skip_reason": reason,
    }
    glance = None
    va_payload = None
    if slides:
        from pipeline.slides.glance import run_slides_v1
        from pipeline.slides.visual_aids import compute_visual_aids_metrics

        glance = run_slides_v1(slides, client=llm_client, language=language)
        if glance:
            payload["slides_v1"] = glance
            glance_path = dest / "slides_v1.json"
            glance_path.write_text(json.dumps(glance, indent=2) + "\n", encoding="utf-8")
            artifacts["slides_v1"] = str(glance_path)
        events = []
        events_path = dest / "vision_events.json"
        if events_path.exists():
            try:
                events = (json.loads(events_path.read_text(encoding="utf-8")) or {}).get("events") or []
            except json.JSONDecodeError:
                events = []
        duration = 1.0
        if slides and slides[0].get("t_end") is not None:
            duration = max(float(slides[-1].get("t_end") or 1.0), 1.0)
        va_payload = compute_visual_aids_metrics(
            payload,
            transcript=transcript,
            vision_events=events,
            duration_s=duration,
            glance=glance,
        )
        if va_payload:
            va_path = dest / "visual_aids_metrics.json"
            va_path.write_text(json.dumps(va_payload, indent=2) + "\n", encoding="utf-8")
            artifacts["visual_aids_metrics"] = str(va_path)
            payload["visual_aids"] = {"slide_count": va_payload.get("slide_count"), "deck_only": va_payload.get("deck_only")}

    slides_path = dest / "slides.json"
    if slides or deck_error:
        slides_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        artifacts["slides"] = str(slides_path)
    elif slides_path.exists():
        slides_path.unlink()

    return SlidesOutput(
        artifacts=artifacts,
        metrics={
            "slide_count": len(slides),
            "has_deck": bool(deck_payload),
            "scene_engine": engine,
            "region_method": region.get("method") if isinstance(region, dict) else None,
            "visual_aids": bool(va_payload),
        },
        skipped=skipped,
        skip_reason=reason,
    )
