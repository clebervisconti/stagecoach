"""Read slide text out of a PPTX zip. PDF text stays on the worker."""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO


_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


def slide_texts_from_pptx(data: bytes) -> list[dict[str, str]]:
    slides: list[dict[str, str]] = []
    with zipfile.ZipFile(BytesIO(data)) as archive:
        names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for name in names:
            root = ET.fromstring(archive.read(name))
            parts = [node.text or "" for node in root.findall(".//a:t", _NS)]
            text = " ".join(part.strip() for part in parts if part.strip())
            if text:
                slides.append({"text": text})
    return slides
