"""Read-only public scoring config (SPEC §7.5)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from app.research import find_repo_file

DEFAULT_VERSION = "1.0.0"


def scoring_yaml_rel(version: str) -> str:
    return f"packages/scoring-config/v{version}/scoring.yaml"


@lru_cache(maxsize=8)
def load_scoring_config(version: str) -> dict[str, Any]:
    if not version or "/" in version or ".." in version:
        raise FileNotFoundError(version)
    path = find_repo_file(scoring_yaml_rel(version))
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FileNotFoundError(version)
    return {
        "version": payload.get("version") or version,
        "readonly": True,
        "config": payload,
    }
