"""Job-scoped LLM settings sidecar. Never writes API keys."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .catalog import normalize_settings

SETTINGS_NAME = "llm_settings.json"


def persist_llm_settings(output_dir: Path, raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    snapshot = normalize_settings(raw)
    path = Path(output_dir) / SETTINGS_NAME
    path.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return snapshot


def load_llm_settings(output_dir: Path) -> dict[str, Any]:
    path = Path(output_dir) / SETTINGS_NAME
    if not path.exists():
        return normalize_settings(None)
    try:
        return normalize_settings(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, TypeError, ValueError):
        return normalize_settings(None)
