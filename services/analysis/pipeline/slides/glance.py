"""slides_v1 Glance Test call (SPEC §6.7.3). At most 20 slides. Approved LLMClient only."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MAX_IMAGES = 20


def _load_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "llm" / "schemas" / "slides_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_slides_v1(
    slides: list[dict[str, Any]],
    *,
    client: Any = None,
    language: str = "en",
) -> Optional[dict[str, Any]]:
    """Return slides_v1 payload or None when the LLM is unavailable.

    Images are counted (≤ 20) and described by path; binary frames are not
    uploaded unless the caller injects a vision-capable client. CI has no key.
    """
    sample = slides[:MAX_IMAGES]
    if not sample:
        return None
    payload_slides = []
    for slide in sample:
        payload_slides.append(
            {
                "index": int(slide.get("index") or 0),
                "title": slide.get("title") or "",
                "word_count": int(slide.get("word_count") or 0),
                "bullet_count": int(slide.get("bullet_count") or 0),
                "keyframe": slide.get("keyframe"),
                "has_image": bool(slide.get("keyframe")),
            }
        )
    if client is None:
        try:
            from llm import LLMClient
            from llm.exceptions import LLMAuthError

            client = LLMClient()
        except Exception as exc:  # no key, missing dep
            logger.info("slides_v1 skipped: %s", type(exc).__name__)
            return None
        try:
            _ = client
        except Exception:
            return None
    try:
        from llm.exceptions import LLMAuthError
    except ImportError:
        LLMAuthError = Exception  # type: ignore
    try:
        response = client.generate_structured(
            prompt_id="slides_v1",
            inputs={
                "language": language,
                "slide_count": len(payload_slides),
                "max_images": MAX_IMAGES,
                "slides": payload_slides,
            },
            schema=_load_schema(),
            temperature=0.3,
        )
        data = getattr(response, "data", response)
        if not isinstance(data, dict):
            return None
        data["image_count"] = min(sum(1 for s in payload_slides if s["has_image"]), MAX_IMAGES)
        return data
    except LLMAuthError:
        logger.info("slides_v1 skipped: no LLM_API_KEY")
        return None
    except Exception:
        logger.info("slides_v1 failed")
        return None
