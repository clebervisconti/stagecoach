"""Parse docs/research/sources.md into the public References payload."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

SOURCE_RE = re.compile(
    r"^\s*-\s+\*\*\[(?P<key>S\d+)\]\*\*\s+(?P<body>.+)$",
    re.MULTILINE,
)
HEADING_RE = re.compile(r"^###\s+(?P<title>.+)$", re.MULTILINE)
URL_RE = re.compile(r"https?://[^\s)]+")


def _candidates(rel: str) -> list[Path]:
    paths: list[Path] = []
    root = os.getenv("STAGECOACH_REPO_ROOT")
    if root:
        paths.append(Path(root) / rel)
    paths.append(Path("/") / rel)
    # Compose mounts: ./docs → /docs and ./packages → /packages
    if rel.startswith("docs/"):
        paths.append(Path("/") / rel)
        paths.append(Path("/docs") / rel.removeprefix("docs/"))
    if rel.startswith("packages/"):
        paths.append(Path("/packages") / rel.removeprefix("packages/"))
    here = Path(__file__).resolve()
    for parent in here.parents:
        paths.append(parent / rel)
    return paths


def find_repo_file(rel: str) -> Path:
    for path in _candidates(rel):
        if path.is_file():
            return path
    raise FileNotFoundError(rel)


def parse_sources(markdown: str) -> list[dict[str, Any]]:
    headings = [(match.start(), match.group("title").strip()) for match in HEADING_RE.finditer(markdown)]
    sources: list[dict[str, Any]] = []
    for match in SOURCE_RE.finditer(markdown):
        key = match.group("key")
        body = match.group("body").strip()
        section = ""
        for start, title in headings:
            if start < match.start():
                section = title
            else:
                break
        sources.append(
            {
                "key": key,
                "anchor": key,
                "section": section,
                "text": body,
                "urls": URL_RE.findall(body),
            }
        )
    return sources


@lru_cache(maxsize=1)
def load_sources() -> dict[str, Any]:
    path = find_repo_file("docs/research/sources.md")
    markdown = path.read_text(encoding="utf-8")
    sources = parse_sources(markdown)
    return {
        "count": len(sources),
        "sources": sources,
        "path": "docs/research/sources.md",
    }
