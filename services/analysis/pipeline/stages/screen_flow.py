"""Screen activity, transitions, and flow metrics for online modes.

Stage mode does not run this stage. Scoring of the numbers waits for E3-5.
Nothing here decides whether a slide is factually correct.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from pipeline.screen.activity import activity_from_video, write_activity_parquet
from pipeline.screen.classify import classify_segments
from pipeline.screen.flow import build_screen_flow
from pipeline.screen.persist import persist_screen_flow
from pipeline.screen.textutil import (
    drop_hallucinated_words,
    load_lexicon,
    speech_spans_from_alignment,
    words_from_transcript,
)
from pipeline.screen.transitions import accept_transitions, scene_cut_times

logger = logging.getLogger(__name__)

STAGE_VERSION = "1.0.0"
WALL_CLOCK_S = 170.0
OCR_CAP = 150

OcrFor = Callable[[float, float], tuple[Any, Any, Any]]


@dataclass
class ScreenFlowOutput:
    artifacts: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: Optional[str] = None
    document: Optional[dict[str, Any]] = None


def screen_flow_skip_reason(
    delivery_mode: str,
    *,
    audio_only: bool,
    video_ready: bool,
) -> Optional[str]:
    """Why this job should not measure the screen. None means run it."""
    if (delivery_mode or "stage") == "stage":
        return "stage_mode"
    if audio_only:
        return "audio_only_chosen"
    if not video_ready:
        return "no_screen"
    return None


def _packages_dir(explicit: Optional[Path]) -> Path:
    if explicit is not None:
        return Path(explicit)
    baked = Path("/packages")
    if (baked / "lexicons" / "en.yaml").is_file():
        return baked
    return Path(__file__).resolve().parents[4] / "packages"


def _read_json(path: Optional[Path]) -> Optional[dict[str, Any]]:
    if path is None or not Path(path).is_file():
        return None
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _screen_offset(output_dir: Path) -> float:
    """screen.mp4 time 0 is the longest screen span's source start."""
    path = output_dir / "screen_spans.json"
    if not path.is_file():
        return 0.0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0.0
    spans = payload if isinstance(payload, list) else []
    best_len = -1.0
    best = 0.0
    for span in spans:
        if not isinstance(span, dict):
            continue
        t0 = float(span.get("t0") or 0.0)
        t1 = span.get("t1")
        length = (float(t1) - t0) if t1 is not None else 0.0
        if length >= best_len:
            best_len = length
            src = span.get("src_t0")
            best = float(src if src is not None else t0)
    return best


def _analysis_window(output_dir: Path, start: float, end: float) -> tuple[float, float]:
    payload = _read_json(output_dir / "layout.json") or {}
    window = payload.get("analysis_window") or {}
    if not isinstance(window, dict):
        return start, end
    raw_start = window.get("t_start", window.get("start_s", window.get("t0")))
    raw_end = window.get("t_end", window.get("end_s", window.get("t1")))
    if raw_start is None or raw_end is None:
        return start, end
    w0 = max(start, float(raw_start))
    w1 = min(end, float(raw_end))
    if w1 <= w0:
        return start, end
    return w0, w1


def _no_video(output_dir: Path) -> list[tuple[float, float]]:
    payload = _read_json(output_dir / "layout.json") or {}
    spans = []
    for segment in payload.get("segments") or []:
        if not isinstance(segment, dict) or segment.get("kind") != "no_video":
            continue
        t0 = float(segment.get("t_start") or 0.0)
        t1 = float(segment.get("t_end") or t0)
        if t1 > t0:
            spans.append((t0, t1))
    return spans


def _camera_visible(output_dir: Path) -> Optional[float]:
    path = output_dir / "camera_spans.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    spans = payload if isinstance(payload, list) else []
    if not spans or not isinstance(spans[0], dict):
        return None
    first = spans[0]
    raw = first.get("src_t0")
    if raw is None:
        raw = first.get("t0")
    return None if raw is None else float(raw)


def _alignment_path(output_dir: Path, session_id: str) -> Optional[Path]:
    for name in (f"{session_id}_alignment.json", "alignment.json"):
        candidate = output_dir / name
        if candidate.is_file():
            return candidate
    return None


def _pauses(output_dir: Path) -> list[dict[str, Any]]:
    payload = _read_json(output_dir / "pauses.json")
    if not payload:
        return []
    rows = payload.get("pauses")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _donor(slides: dict[str, Any], start: float, end: float) -> Optional[tuple[str, int, Any]]:
    best = None
    best_overlap = 0.0
    for slide in slides.get("slides") or []:
        if not isinstance(slide, dict) or slide.get("t_start") is None:
            continue
        slide_end = slide.get("t_end")
        if slide_end is None:
            continue
        overlap = min(float(slide_end), end) - max(float(slide["t_start"]), start)
        text = str(slide.get("text") or "")
        words = int(slide.get("word_count") or len(text.split()))
        if words < 3 or overlap <= best_overlap:
            continue
        best_overlap = overlap
        best = (text, words, slide.get("deck_page"))
    return best


def _shift(value: float, offset: float) -> float:
    return round(float(value) + offset, 3)


def _apply_offset(rows: list[dict[str, Any]], transitions: list[dict[str, Any]], segments: list[dict[str, Any]], offset: float) -> None:
    if not offset:
        return
    for row in rows:
        row["t"] = _shift(row["t"], offset)
    for item in transitions:
        item["t"] = _shift(item["t"], offset)
    for segment in segments:
        segment["t_start"] = _shift(segment["t_start"], offset)
        segment["t_end"] = _shift(segment["t_end"], offset)


def _ocr_engine(injected: bool, used_donor: bool) -> str:
    if injected:
        return "provided"
    if used_donor:
        return "slides"
    return "tesseract"


def _sync_slides(
    output_dir: Path,
    *,
    session_id: str,
    segments: list[dict[str, Any]],
    keyframe_paths: dict[int, str],
    transcript: Optional[dict[str, Any]],
    words: list[dict[str, Any]],
    transition_engine: str,
    camera_setup: str,
) -> None:
    """Replace timed scenes so the existing Slides tab keeps its shape.

    The glance already stored for this job is reused. This stage does not
    call a language model.
    """
    dest = output_dir / "slides.json"
    previous = _read_json(dest) or {}
    slides = []
    for segment in segments:
        text = str(segment.get("ocr_text") or "")
        lines = [line for line in text.splitlines() if line.strip()]
        title = lines[0] if lines else ""
        index = int(segment["index"])
        spoken = " ".join(
            str(word.get("text") or "")
            for word in words
            if float(segment["t_start"]) <= float(word["start"]) < float(segment["t_end"])
        )
        overlap = None
        if text and spoken:
            try:
                from pipeline.slides.match import reading_overlap

                overlap = reading_overlap(text, spoken)
            except Exception:
                overlap = None
        slides.append(
            {
                "index": index,
                "t_start": segment["t_start"],
                "t_end": segment["t_end"],
                "dwell_s": segment["dwell_s"],
                "keyframe": keyframe_paths.get(index),
                "text": text,
                "title": title,
                "word_count": int(segment.get("ocr_word_count") or len(text.split())),
                "bullet_count": sum(1 for line in lines[1:] if line.lstrip()[:1] in {"•", "-", "*", "·"}),
                "ocr_engine": segment.get("ocr_engine"),
                "deck_page": segment.get("deck_page"),
                "match_method": "screen_flow",
                "match_score": None,
                "reading_overlap": overlap,
                "region": previous.get("region"),
                "segment_type": segment.get("type"),
            }
        )
    payload = {
        "version": previous.get("version") or "1.0.0",
        "session_id": session_id,
        "cpu_only": True,
        "paddleocr": False,
        "pyscenedetect": "pyscenedetect" in transition_engine,
        "scene_engine": transition_engine,
        "region": previous.get("region"),
        "camera_setup": previous.get("camera_setup") or camera_setup,
        "deck_error": previous.get("deck_error"),
        "slides": slides,
        "slide_count": len(slides),
        "skip_reason": None if slides else "No screen segments.",
    }
    if previous.get("slides_v1"):
        payload["slides_v1"] = previous["slides_v1"]
    dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if not slides:
        return
    try:
        from pipeline.slides.visual_aids import compute_visual_aids_metrics

        events = []
        events_path = output_dir / "vision_events.json"
        if events_path.is_file():
            events = (_read_json(events_path) or {}).get("events") or []
        duration = max(float(slides[-1].get("t_end") or 1.0), 1.0)
        metrics = compute_visual_aids_metrics(
            payload,
            transcript=transcript,
            vision_events=events,
            duration_s=duration,
            glance=previous.get("slides_v1"),
        )
        if metrics:
            va_path = output_dir / "visual_aids_metrics.json"
            va_path.write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
            payload["visual_aids"] = {
                "slide_count": metrics.get("slide_count"),
                "deck_only": metrics.get("deck_only"),
            }
            dest.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except Exception:
        logger.exception("visual aids refresh failed session=%s", session_id)


def run_screen_flow(
    *,
    output_dir: Path,
    session_id: str,
    job_id: str,
    video_path: Path,
    delivery_mode: str,
    language: str = "en",
    packages_dir: Optional[Path] = None,
    transcript_path: Optional[Path] = None,
    deadline_s: float = WALL_CLOCK_S,
    ocr_by_segment: Optional[OcrFor] = None,
    write_keyframes: bool = True,
) -> ScreenFlowOutput:
    """Measure one online job. Writes screen_flow.json and activity.parquet."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    reason = screen_flow_skip_reason(
        delivery_mode,
        audio_only=False,
        video_ready=Path(video_path).is_file(),
    )
    if reason:
        return ScreenFlowOutput(skipped=True, skip_reason=reason)
    try:
        import cv2  # noqa: F401
    except ImportError:
        return ScreenFlowOutput(skipped=True, skip_reason="opencv_missing")

    deadline = time.monotonic() + max(float(deadline_s), 1.0)
    rows, crop_duration, truncated = activity_from_video(Path(video_path), deadline=deadline)
    offset = _screen_offset(output_dir)
    engine = "ssim"
    scene_cuts: list[float] = []
    if time.monotonic() + 5.0 < deadline:
        scene_cuts = scene_cut_times(video_path)
        engine = "ssim+pyscenedetect"
    transitions = accept_transitions(rows, scene_cuts)
    slides_payload = _read_json(output_dir / "slides.json") or {}
    ocr_calls = 0
    used_donor = False
    keyframe_dir = output_dir / "screen_keyframes"

    def ocr_for(start: float, end: float) -> tuple[str, int, Any]:
        nonlocal ocr_calls, used_donor, truncated
        if time.monotonic() > deadline:
            truncated = True
            return "", 0, None
        donor = _donor(slides_payload, start + offset, end + offset)
        if donor and int(donor[1]) >= 3:
            used_donor = True
            return donor
        if ocr_by_segment is not None:
            found = ocr_by_segment(start, end) or ("", 0, None)
            text = str(found[0] or "")
            count = int(found[1] if found[1] is not None else len(text.split()))
            return text, count, found[2]
        if ocr_calls >= OCR_CAP:
            truncated = True
            return "", 0, None
        ocr_calls += 1
        try:
            from pipeline.slides.keyframes import extract_keyframe
            from pipeline.slides.ocr import ocr_image

            keyframe_dir.mkdir(parents=True, exist_ok=True)
            dest = keyframe_dir / f"ocr_{ocr_calls:03d}.jpg"
            extracted = extract_keyframe(Path(video_path), start, end, dest)
            if not extracted.get("path"):
                return "", 0, None
            recognized = ocr_image(Path(extracted["path"]), language=language)
            text = str(recognized.get("text") or "")
            return text, len(text.split()), None
        except Exception:
            logger.info("screen ocr failed session=%s", session_id)
            return "", 0, None

    segments = classify_segments(
        rows,
        [float(item["t"]) for item in transitions],
        crop_duration if crop_duration > 0 else (float(rows[-1]["t"]) + 1.0 if rows else 0.0),
        ocr_for=ocr_for,
    )
    keyframe_paths: dict[int, str] = {}
    if write_keyframes and segments and time.monotonic() < deadline:
        try:
            from pipeline.slides.keyframes import extract_keyframe

            keyframe_dir.mkdir(parents=True, exist_ok=True)
            for segment in segments[:OCR_CAP]:
                if time.monotonic() > deadline:
                    truncated = True
                    break
                index = int(segment["index"])
                relative = f"screen_keyframes/scr_{index:03d}.jpg"
                extracted = extract_keyframe(
                    Path(video_path),
                    float(segment["t_start"]),
                    float(segment["t_end"]),
                    output_dir / relative,
                )
                if extracted.get("path"):
                    segment["keyframe"] = relative
                    keyframe_paths[index] = str(output_dir / relative)
        except Exception:
            logger.info("screen keyframe failed session=%s", session_id)

    _apply_offset(rows, transitions, segments, offset)
    source_end = offset + (crop_duration if crop_duration > 0 else 0.0)
    window = _analysis_window(output_dir, offset, source_end if source_end > offset else offset)
    transcript = _read_json(Path(transcript_path) if transcript_path else None)
    if transcript is None:
        transcript = _read_json(output_dir / "transcript.json")
    raw_words = words_from_transcript(transcript)
    alignment = _read_json(_alignment_path(output_dir, session_id))
    vad_known = isinstance(alignment, dict) and isinstance(alignment.get("vad_segments"), list)
    speech = speech_spans_from_alignment(alignment) if vad_known else []
    if vad_known:
        words, dropped = drop_hallucinated_words(raw_words, speech, max(window[1], source_end, 0.0))
    else:
        words, dropped = raw_words, 0
    lexicon = load_lexicon(language, _packages_dir(packages_dir))
    screen_visible = max(0.0, window[1] - window[0]) if source_end > offset else 0.0
    if crop_duration > 0:
        screen_visible = max(0.0, min(source_end, window[1]) - max(offset, window[0]))
    document = build_screen_flow(
        delivery_mode=delivery_mode,
        language=language,
        activity=rows,
        transitions=transitions,
        segments=segments,
        words=words,
        pauses=_pauses(output_dir),
        speech=speech,
        window=window,
        screen_visible_s=screen_visible,
        lexicon=lexicon,
        asr_dropped_words=dropped,
        transition_engine=engine,
        ocr_engine=_ocr_engine(ocr_by_segment is not None, used_donor),
        vad_source="alignment" if vad_known else "missing",
        no_video=_no_video(output_dir),
        camera_visible_s=_camera_visible(output_dir),
        truncated=truncated,
        vad_known=vad_known,
    )
    flow_path = output_dir / "screen_flow.json"
    flow_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    parquet_path = output_dir / "screen_activity.parquet"
    write_activity_parquet(parquet_path, rows)
    if segments:
        try:
            _sync_slides(
                output_dir,
                session_id=session_id,
                segments=segments,
                keyframe_paths=keyframe_paths,
                transcript=transcript,
                words=words,
                transition_engine=engine,
                camera_setup="screen_recording",
            )
        except Exception:
            logger.exception("slides.json sync failed session=%s", session_id)
    persist_screen_flow(
        job_id=job_id,
        session_id=session_id,
        document=document,
        artifact_uri=str(flow_path),
    )
    return ScreenFlowOutput(
        artifacts={"screen_flow": str(flow_path), "screen_activity": str(parquet_path)},
        metrics={
            "segment_count": len(document.get("segments") or []),
            "transition_engine": engine,
            "asr_dropped_words": dropped,
            "truncated": truncated,
            "content_judgment": False,
        },
        document=document,
    )
