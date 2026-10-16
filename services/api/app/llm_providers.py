"""User-visible LLM provider catalog (owner decision 2026-10-16).

Default is the local OpenAI-compatible endpoint (LM Studio on TIGER).
xAI stays selectable. Keys are never accepted or stored.
"""

from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_PROVIDER = "local"
DEFAULT_LOCAL_MODEL = "qwen/qwen3.8-27b"
FALLBACK_LOCAL_BASE_URL = "http://127.0.0.1:1234/v1"
PROVIDER_IDS = ("local", "xai", "anthropic", "openai", "gemini", "custom")
CLOUD_WARNING = frozenset({"xai", "anthropic", "openai", "gemini", "custom"})
LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})
KEY_ENVS = {
    "local": ("LOCAL_LLM_API_KEY",),
    "xai": ("XAI_API_KEY", "LLM_API_KEY"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "custom": ("CUSTOM_LLM_API_KEY", "LLM_API_KEY"),
}
DEFAULT_BASE_URLS = {
    "xai": "https://api.x.ai/v1",
    "local": FALLBACK_LOCAL_BASE_URL,
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "custom": "",
}
DEFAULT_MODELS = {
    "local": DEFAULT_LOCAL_MODEL,
    "xai": "grok-beta",
    "anthropic": "claude-sonnet-4-5",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "custom": "",
}


def local_base_url() -> str:
    return (os.getenv("LOCAL_LLM_BASE_URL") or FALLBACK_LOCAL_BASE_URL).strip().rstrip("/")


def default_base_url(provider: str) -> str:
    choice = normalize_provider_id(provider)
    if choice == "local":
        return local_base_url()
    return DEFAULT_BASE_URLS[choice]


def default_model(provider: str) -> str:
    return DEFAULT_MODELS[normalize_provider_id(provider)]


def normalize_provider_id(value: Optional[str]) -> str:
    if value in (None, ""):
        return DEFAULT_PROVIDER
    if value not in PROVIDER_IDS:
        raise ValueError(f"Unknown LLM provider: {value}")
    return value


def is_loopback_url(url: Optional[str]) -> bool:
    if not url:
        return False
    return (urlparse(url).hostname or "").lower() in LOOPBACK_HOSTS


def leaves_machine(provider: Optional[str], base_url: Optional[str] = None) -> bool:
    choice = normalize_provider_id(provider)
    if choice == "local":
        return not is_loopback_url(base_url or local_base_url())
    if choice == "custom":
        return not is_loopback_url(base_url)
    return choice in CLOUD_WARNING


def normalize_llm_settings(raw: Optional[dict]) -> dict[str, Any]:
    src = raw or {}
    forbidden = [
        key
        for key in src
        if "key" in str(key).lower() or "secret" in str(key).lower() or "token" in str(key).lower()
    ]
    if forbidden:
        raise ValueError(f"API keys must not be stored in settings: {forbidden}")
    raw_provider = src.get("provider") if isinstance(src.get("provider"), str) else None
    provider = normalize_provider_id(raw_provider)
    base_url = str(src.get("base_url") or "").strip()
    model = str(src.get("model") or "").strip()
    if provider in {"local", "custom"} and not base_url:
        base_url = default_base_url(provider)
    if not model:
        model = default_model(provider)
    return {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "leaves_machine": leaves_machine(provider, base_url),
    }


def key_configured(provider: str) -> bool:
    choice = normalize_provider_id(provider)
    if choice == "local":
        return True
    return any(os.environ.get(name, "").strip() for name in KEY_ENVS[choice])


def provider_catalog() -> dict[str, Any]:
    entries = []
    for provider_id in PROVIDER_IDS:
        entries.append(
            {
                "id": provider_id,
                "default": provider_id == DEFAULT_PROVIDER,
                "leaves_machine": leaves_machine(provider_id, default_base_url(provider_id)),
                "key_envs": list(KEY_ENVS[provider_id]),
                "key_configured": key_configured(provider_id),
                "needs_base_url": provider_id in {"local", "custom"},
                "default_base_url": default_base_url(provider_id),
                "default_model": default_model(provider_id),
            }
        )
    return {"default_provider": DEFAULT_PROVIDER, "providers": entries}
