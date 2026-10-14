"""Tesseract OCR (Apache-2.0) with eng/por traineddata [S48]. PaddleOCR is not used."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def ocr_image(path: Path, *, language: str = "en") -> dict[str, Optional[str]]:
    """OCR one keyframe. Returns empty text when Tesseract is missing (not a fake score)."""
    if not path.exists() or path.stat().st_size == 0:
        return {"text": "", "engine": None, "lang": None, "error": "no_image"}
    if not tesseract_available():
        return {"text": "", "engine": None, "lang": None, "error": "tesseract_missing"}
    lang = "por+eng" if language.startswith("pt") else "eng+por"
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {"text": "", "engine": None, "lang": None, "error": "pytesseract_missing"}
    try:
        text = pytesseract.image_to_string(Image.open(path), lang=lang) or ""
    except Exception as exc:  # Tesseract traineddata missing, etc.
        logger.info("tesseract failed: %s", type(exc).__name__)
        return {"text": "", "engine": "tesseract", "lang": lang, "error": type(exc).__name__}
    return {"text": text.strip(), "engine": "tesseract", "lang": lang, "error": None}
