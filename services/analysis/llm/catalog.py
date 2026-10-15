"""Approved LLM providers (owner decision 2026-10-14).

xAI (Grok) stays the default. Keys are resolved from environment or a secret
manager only — never from the repo or from user-submitted form fields.
"""

from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_PROVIDER = "xai"

PROVIDER_IDS = (
    "xai",
    "local",
    "anthropic",
    "openai",
    "gemini",
    "custom",
)

KEY_ENVS = {
    "xai": ("XAI_API_KEY", "LLM_API_KEY"),
    "local": ("LOCAL_LLM_API_KEY", "LLM_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "custom": ("CUSTOM_LLM_API_KEY", "LLM_API_KEY"),
}

DEFAULT_BASE_URLS = {
    "xai": "https://api.x.ai/v1",
    "local": "http://127.0.0.1:1234/v1",
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "custom": "",
}

DEFAULT_MODELS = {
    "xai": "grok-beta",
    "local": "gemma-3-12b",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "custom": "default",
}

# Cloud vendors other than the owner-chosen default. Local / loopback stay on-box.
CLOUD_WARNING_PROVIDERS = frozenset({"anthropic", "openai", "gemini", "custom"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def normalize_provider_id(value: Optional[str]) -> str:
    if value in (None, ""):
        return DEFAULT_PROVIDER
    if value not in PROVIDER_IDS:
        raise ValueError(f"Unknown LLM provider: {value}")
    return value


def is_loopback_url(url: Optional[str]) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host in LOOPBACK_HOSTS


def leaves_machine(provider: Optional[str], base_url: Optional[str] = None) -> bool:
    """True when analysis text would be sent to a non-default cloud host."""
    choice = normalize_provider_id(provider)
    if choice == "xai":
        return False
    if choice == "local":
        return not is_loopback_url(base_url or DEFAULT_BASE_URLS["local"])
    if choice == "custom":
        return not is_loopback_url(base_url)
    return choice in CLOUD_WARNING_PROVIDERS


def key_envs_for(provider: str) -> tuple[str, ...]:
    return KEY_ENVS[normalize_provider_id(provider)]


def default_base_url(provider: str) -> str:
    return DEFAULT_BASE_URLS[normalize_provider_id(provider)]


def default_model(provider: str) -> str:
    return DEFAULT_MODELS[normalize_provider_id(provider)]


def catalog_entries() -> list[dict[str, Any]]:
    return [
        {
            "id": "xai",
            "label": "xAI (Grok)",
            "kind": "cloud_default",
            "leaves_machine": False,
            "key_envs": list(KEY_ENVS["xai"]),
            "default_base_url": DEFAULT_BASE_URLS["xai"],
            "default_model": DEFAULT_MODELS["xai"],
            "needs_base_url": False,
        },
        {
            "id": "local",
            "label": "Local OpenAI-compatible (LM Studio / Gemma)",
            "kind": "local",
            "leaves_machine": False,
            "key_envs": list(KEY_ENVS["local"]),
            "default_base_url": DEFAULT_BASE_URLS["local"],
            "default_model": DEFAULT_MODELS["local"],
            "needs_base_url": True,
        },
        {
            "id": "anthropic",
            "label": "Anthropic Claude",
            "kind": "cloud",
            "leaves_machine": True,
            "key_envs": list(KEY_ENVS["anthropic"]),
            "default_base_url": DEFAULT_BASE_URLS["anthropic"],
            "default_model": DEFAULT_MODELS["anthropic"],
            "needs_base_url": False,
        },
        {
            "id": "openai",
            "label": "OpenAI",
            "kind": "cloud",
            "leaves_machine": True,
            "key_envs": list(KEY_ENVS["openai"]),
            "default_base_url": DEFAULT_BASE_URLS["openai"],
            "default_model": DEFAULT_MODELS["openai"],
            "needs_base_url": False,
        },
        {
            "id": "gemini",
            "label": "Google Gemini",
            "kind": "cloud",
            "leaves_machine": True,
            "key_envs": list(KEY_ENVS["gemini"]),
            "default_base_url": DEFAULT_BASE_URLS["gemini"],
            "default_model": DEFAULT_MODELS["gemini"],
            "needs_base_url": False,
        },
        {
            "id": "custom",
            "label": "Custom OpenAI-compatible URL",
            "kind": "custom",
            "leaves_machine": True,
            "key_envs": list(KEY_ENVS["custom"]),
            "default_base_url": "",
            "default_model": DEFAULT_MODELS["custom"],
            "needs_base_url": True,
        },
    ]


def normalize_settings(raw: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Keep provider / URL / model only. Reject key-shaped fields."""
    src = raw or {}
    forbidden = [key for key in src if "key" in key.lower() or "secret" in key.lower() or "token" in key.lower()]
    if forbidden:
        raise ValueError(f"API keys must not be stored in settings: {forbidden}")
    provider = normalize_provider_id(src.get("provider") if isinstance(src.get("provider"), str) else None)
    base_url = str(src.get("base_url") or "").strip()
    model = str(src.get("model") or "").strip()
    if provider in {"local", "custom"} and not base_url:
        base_url = default_base_url(provider)
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "leaves_machine": leaves_machine(provider, base_url),
    }
