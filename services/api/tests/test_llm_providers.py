"""LLM provider settings (owner decision 2026-10-16). No live calls."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from fastapi import HTTPException

from app.llm_providers import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_PROVIDER,
    key_configured,
    leaves_machine,
    normalize_llm_settings,
    provider_catalog,
)
from app.routers.users import parse_llm_settings


def test_default_is_local_qwen(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert DEFAULT_PROVIDER == "local"
    settings = normalize_llm_settings(None)
    assert settings["provider"] == "local"
    assert settings["model"] == DEFAULT_LOCAL_MODEL
    assert settings["base_url"] == "http://127.0.0.1:1234/v1"
    assert settings["leaves_machine"] is False
    assert key_configured("local") is True
    catalog = provider_catalog()
    assert catalog["default_provider"] == "local"
    local = next(row for row in catalog["providers"] if row["id"] == "local")
    assert local["default"] is True


def test_local_base_url_from_env(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://tiger.local:1234/v1")
    settings = normalize_llm_settings(None)
    assert settings["base_url"] == "http://tiger.local:1234/v1"
    catalog = provider_catalog()
    local = next(row for row in catalog["providers"] if row["id"] == "local")
    assert local["default_base_url"] == "http://tiger.local:1234/v1"


def test_boots_without_xai_key(monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    catalog = provider_catalog()
    xai = next(row for row in catalog["providers"] if row["id"] == "xai")
    assert xai["default"] is False
    assert xai["key_configured"] is False
    assert key_configured("xai") is False
    # Default catalog still builds — no startup requirement for XAI_API_KEY.
    assert catalog["default_provider"] == "local"


def test_xai_is_selectable_and_leaves_the_machine():
    settings = normalize_llm_settings({"provider": "xai"})
    assert settings["provider"] == "xai"
    assert leaves_machine("xai") is True
    assert settings["leaves_machine"] is True
    ids = {row["id"] for row in provider_catalog()["providers"]}
    assert "xai" in ids


def test_cloud_warning_and_local_loopback():
    assert leaves_machine("openai") is True
    assert leaves_machine("local", "http://127.0.0.1:1234/v1") is False


def test_rejects_api_keys_in_settings():
    with pytest.raises(HTTPException) as exc:
        parse_llm_settings({"provider": "openai", "api_key": "sk-test"})
    assert exc.value.status_code == 422
    assert "key" in str(exc.value.detail).lower()


def test_catalog_never_includes_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-appear")
    catalog = provider_catalog()
    blob = str(catalog)
    assert "sk-should-not-appear" not in blob
    openai = next(row for row in catalog["providers"] if row["id"] == "openai")
    assert openai["key_configured"] is True
    assert openai["leaves_machine"] is True
