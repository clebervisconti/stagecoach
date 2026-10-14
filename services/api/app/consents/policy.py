"""Versioned consent policy texts (SPEC §5.4, §10.2)."""

from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

CONSENT_PURPOSES = (
    "video_analysis",
    "expression_analysis",
    "keep_detailed_tracking",
    "research_use",
    "benchmarks",
)
UI_PURPOSES = (
    "video_analysis",
    "expression_analysis",
    "keep_detailed_tracking",
)
LOCALES = ("en", "pt-BR")
POLICY_ID = "1.0.0"


def find_policy_path() -> Path:
    env = os.getenv("CONSENT_POLICY_PATH")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    candidates = [Path("/packages/consent/v1.json")]
    for parent in here.parents:
        candidates.append(parent / "packages" / "consent" / "v1.json")
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("packages/consent/v1.json was not found")


@lru_cache(maxsize=1)
def load_policy() -> dict[str, Any]:
    return json.loads(find_policy_path().read_text(encoding="utf-8"))


def policy_version(policy: dict[str, Any] | None = None) -> str:
    payload = policy if policy is not None else load_policy()
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def localize_purpose(purpose: str, locale: str, policy: dict[str, Any] | None = None) -> dict[str, str]:
    texts = (policy or load_policy())["purposes"][purpose]
    chosen = locale if locale in texts else "en"
    block = texts[chosen]
    return {
        "title": block["title"],
        "what": block["what"],
        "why": block["why"],
        "limits": block["limits"],
        "never": block["never"],
    }
