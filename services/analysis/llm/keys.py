"""Resolve provider API keys from the environment or an explicit secret.

Never read keys from the repo, config files, or user settings JSON.
"""

from __future__ import annotations

import os
from typing import Optional

from .catalog import KEY_ENVS, normalize_provider_id
from .exceptions import LLMAuthError


def resolve_api_key(provider: str, explicit: Optional[str] = None) -> str:
    if explicit is not None and str(explicit).strip():
        return str(explicit).strip()
    choice = normalize_provider_id(provider)
    for env_name in KEY_ENVS[choice]:
        raw = os.environ.get(env_name, "").strip()
        if raw:
            return raw
    if choice == "local":
        return "local"
    names = " or ".join(KEY_ENVS[choice])
    raise LLMAuthError(
        f"{names} is not set. Keys come from the environment or a secret manager, never the repo."
    )


def key_is_configured(provider: str) -> bool:
    choice = normalize_provider_id(provider)
    if choice == "local":
        return True
    return any(os.environ.get(name, "").strip() for name in KEY_ENVS[choice])
