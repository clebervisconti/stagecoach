"""LLM provider catalog and stand-in transports — no live network (ADR-060)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from llm.catalog import (
    DEFAULT_LOCAL_MODEL,
    DEFAULT_PROVIDER,
    leaves_machine,
    normalize_provider_id,
    normalize_settings,
)
from llm.client import LLMClient
from llm.exceptions import LLMAuthError
from llm.keys import key_is_configured, resolve_api_key
from llm.providers.anthropic import AnthropicProvider
from llm.providers.openai_compat import OpenAICompatibleProvider
from llm.settings import persist_llm_settings
from llm.transport import StandinTransport

SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}

COMPAT_REPLY = {
    "choices": [{"message": {"content": '{"summary": "ok"}'}}],
    "usage": {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
}

ANTHROPIC_REPLY = {
    "content": [{"type": "text", "text": '{"summary": "ok"}'}],
    "usage": {"input_tokens": 3, "output_tokens": 2},
}


def test_default_is_local_qwen(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    assert normalize_provider_id(None) == "local" == DEFAULT_PROVIDER
    settings = normalize_settings(None)
    assert settings["provider"] == "local"
    assert settings["model"] == DEFAULT_LOCAL_MODEL
    assert settings["base_url"] == "http://127.0.0.1:1234/v1"
    assert leaves_machine("local", settings["base_url"]) is False


def test_cloud_others_leave_the_machine():
    assert leaves_machine("xai") is True
    assert leaves_machine("openai") is True
    assert leaves_machine("anthropic") is True
    assert leaves_machine("gemini") is True
    assert leaves_machine("custom", "https://vendor.example/v1") is True
    assert leaves_machine("local", "http://127.0.0.1:1234/v1") is False
    assert leaves_machine("custom", "http://localhost:1234/v1") is False


def test_settings_reject_api_keys():
    with pytest.raises(ValueError, match="API keys"):
        normalize_settings({"provider": "xai", "api_key": "sk-live"})


def test_local_key_is_optional(monkeypatch):
    monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    assert resolve_api_key("local") == "local"
    assert key_is_configured("local") is True
    assert key_is_configured("xai") is False
    with pytest.raises(LLMAuthError, match="XAI_API_KEY"):
        resolve_api_key("xai")
    with pytest.raises(LLMAuthError, match="OPENAI_API_KEY"):
        resolve_api_key("openai")


def test_client_boots_without_xai_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
    persist_llm_settings(tmp_path, None)
    transport = StandinTransport(COMPAT_REPLY)
    client = LLMClient(
        settings_path=tmp_path / "llm_settings.json",
        use_cassettes=False,
        transport=transport,
    )
    assert client.provider_name == "local"
    assert client.api_key == "local"
    out = client.generate_structured("t", {"n": 1}, SCHEMA)
    assert out.data["summary"] == "ok"


def test_xai_still_selectable_with_key(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "stand-in-key")
    persist_llm_settings(tmp_path, {"provider": "xai"})
    transport = StandinTransport(COMPAT_REPLY)
    client = LLMClient(
        settings_path=tmp_path / "llm_settings.json",
        use_cassettes=False,
        transport=transport,
    )
    assert client.provider_name == "xai"
    out = client.generate_structured("t", {"n": 1}, SCHEMA)
    assert out.data["summary"] == "ok"
    assert json.loads((tmp_path / "llm_settings.json").read_text())["provider"] == "xai"
    assert "stand-in-key" not in (tmp_path / "llm_settings.json").read_text()


def test_openai_compat_standin_never_opens_a_socket():
    transport = StandinTransport(COMPAT_REPLY)
    provider = OpenAICompatibleProvider(
        api_key="stand-in",
        base_url="https://example.invalid/v1",
        models={"gpt-4o-mini": {"temperature_default": 0.1, "price_per_input_token": 0, "price_per_output_token": 0}},
        timeout=5,
        retry_config={"max_attempts": 1, "backoff_factor": 1},
        provider_id="openai",
        transport=transport,
    )
    response = provider.generate_structured("t", {"n": 1}, SCHEMA, "gpt-4o-mini")
    assert response.data["summary"] == "ok"
    assert response.usage.provider == "openai"
    assert transport.calls[0]["url"].endswith("/chat/completions")
    assert transport.calls[0]["headers"]["Authorization"] == "<redacted>"


def test_anthropic_standin():
    transport = StandinTransport(ANTHROPIC_REPLY)
    provider = AnthropicProvider(
        api_key="stand-in",
        base_url="https://api.anthropic.invalid",
        models={},
        timeout=5,
        retry_config={"max_attempts": 1, "backoff_factor": 1},
        transport=transport,
    )
    response = provider.generate_structured("t", {}, SCHEMA, "claude-sonnet-4-5")
    assert response.usage.provider == "anthropic"
    assert transport.calls[0]["url"].endswith("/v1/messages")
    assert transport.calls[0]["headers"]["x-api-key"] == "<redacted>"


def test_sidecar_never_writes_keys(tmp_path: Path):
    with pytest.raises(ValueError):
        persist_llm_settings(tmp_path, {"provider": "openai", "openai_api_key": "sk"})
