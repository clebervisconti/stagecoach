"""LLM provider settings (owner decision 2026-10-14). No live calls."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://stagecoach@127.0.0.1/stagecoach_test")

import pytest
from fastapi import HTTPException

from app.llm_providers import (
    DEFAULT_PROVIDER,
    leaves_machine,
    normalize_llm_settings,
    provider_catalog,
)
from app.routers.users import parse_llm_settings


def test_default_is_xai():
    assert normalize_llm_settings(None)["provider"] == DEFAULT_PROVIDER
    assert leaves_machine("xai") is False


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
