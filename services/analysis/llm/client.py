"""LLM Client: Provider-neutral interface for structured LLM calls

Per ADR-007 / ADR-060: adapters, cost tracking, cassettes. Keys from env only.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from .catalog import (
    DEFAULT_PROVIDER,
    default_base_url,
    default_model,
    normalize_provider_id,
    normalize_settings,
)
from .exceptions import LLMAuthError, LLMCostExceededError
from .keys import resolve_api_key
from .providers.anthropic import AnthropicProvider
from .providers.base import BaseLLMProvider
from .providers.openai_compat import OpenAICompatibleProvider
from .providers.xai import XAIProvider
from .transport import HttpTransport
from .types import LLMResponse, UsageStats

OPENAI_COMPAT = frozenset({"xai", "local", "openai", "gemini", "custom"})


class LLMClient:
    """
    Provider-neutral LLM client with structured output support.

    Usage:
        client = LLMClient()
        response = client.generate_structured(
            prompt_id="message_v1",
            inputs={"context_type": "keynote", "segments": [...]},
            schema=message_v1_schema
        )
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        provider_name: Optional[str] = None,
        use_cassettes: Optional[bool] = None,
        settings_path: Optional[Path] = None,
        base_url: Optional[str] = None,
        transport: Optional[HttpTransport] = None,
    ):
        if config_path is None:
            config_path = Path(__file__).parent.parent / "config" / "llm.yaml"
        with open(config_path) as handle:
            self.config = yaml.safe_load(handle)

        sidecar = _load_sidecar(settings_path)
        self.provider_name = normalize_provider_id(
            provider_name
            or sidecar.get("provider")
            or os.getenv("LLM_PROVIDER")
            or self.config.get("default_provider")
            or DEFAULT_PROVIDER
        )
        if self.provider_name not in self.config.get("providers", {}):
            raise ValueError(f"Provider {self.provider_name} not found in config")

        local_env = (
            os.getenv("LOCAL_LLM_BASE_URL", "").strip() if self.provider_name == "local" else ""
        )
        self.base_url = (
            (base_url or "").strip()
            or (sidecar.get("base_url") or "").strip()
            or local_env
            or os.getenv("LLM_BASE_URL", "").strip()
            or self.config["providers"][self.provider_name].get("base_url")
            or default_base_url(self.provider_name)
        )
        if self.provider_name == "custom" and not self.base_url:
            raise ValueError("custom provider requires a base_url (settings or LLM_BASE_URL)")

        self.model_override = (sidecar.get("model") or "").strip() or None
        self.api_key = resolve_api_key(self.provider_name, api_key)
        provider_config = dict(self.config["providers"][self.provider_name])
        provider_config["base_url"] = self.base_url
        self.provider: BaseLLMProvider = self._create_provider(
            self.provider_name, provider_config, transport=transport
        )

        self.use_cassettes = (
            use_cassettes if use_cassettes is not None else self.config["cassettes"]["enabled"]
        )
        self.cassette_dir = Path(self.config["cassettes"]["directory"])
        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.total_cost = 0.0
        self.cost_ceiling = self.config["cost_ceiling_per_analysis"]

    def _create_provider(
        self,
        provider_name: str,
        provider_config: dict[str, Any],
        transport: Optional[HttpTransport] = None,
    ) -> BaseLLMProvider:
        kwargs = {
            "api_key": self.api_key,
            "base_url": provider_config["base_url"],
            "models": provider_config.get("models") or {},
            "timeout": 180 if provider_name == "local" else self.config["timeout"]["default"],
            "retry_config": self.config["retry"],
            "transport": transport,
        }
        if provider_name == "xai":
            return XAIProvider(**kwargs)
        if provider_name == "anthropic":
            return AnthropicProvider(**kwargs)
        if provider_name in OPENAI_COMPAT:
            return OpenAICompatibleProvider(provider_id=provider_name, **kwargs)
        raise ValueError(f"Unknown provider: {provider_name}")

    def generate_structured(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        schema: dict[str, Any],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        if self.use_cassettes:
            cassette_response = self._try_load_cassette(prompt_id, inputs, schema)
            if cassette_response:
                return cassette_response

        if self.total_cost >= self.cost_ceiling:
            raise LLMCostExceededError(
                f"Cost ceiling of ${self.cost_ceiling:.2f} exceeded "
                f"(current: ${self.total_cost:.4f})"
            )

        model = (
            model
            or self.model_override
            or self.config["model_assignments"].get(prompt_id)
            or self.config["model_assignments"].get("default")
            or default_model(self.provider_name)
        )
        assigned = self.config["providers"][self.provider_name].get("models") or {}
        if model not in assigned:
            model = default_model(self.provider_name)

        response = self.provider.generate_structured(
            prompt_id=prompt_id,
            inputs=inputs,
            schema=schema,
            model=model,
            temperature=temperature,
        )
        self.total_cost += response.usage.cost_usd
        if self.use_cassettes:
            self._save_cassette(prompt_id, inputs, schema, response)
        return response

    def _try_load_cassette(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        schema: dict[str, Any],
    ) -> Optional[LLMResponse]:
        cassette_key = self._cassette_key(prompt_id, inputs, schema)
        cassette_path = self.cassette_dir / f"{cassette_key}.json"
        if not cassette_path.exists():
            return None
        with open(cassette_path) as handle:
            cassette_data = json.load(handle)
        return LLMResponse(
            data=cassette_data["data"],
            usage=UsageStats(**cassette_data["usage"]),
            raw_response=cassette_data["raw_response"],
            prompt_id=cassette_data["prompt_id"],
            prompt_version=cassette_data["prompt_version"],
            model=cassette_data["model"],
            temperature=cassette_data["temperature"],
            created_at=datetime.fromisoformat(cassette_data["created_at"]),
        )

    def _save_cassette(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        schema: dict[str, Any],
        response: LLMResponse,
    ) -> None:
        cassette_key = self._cassette_key(prompt_id, inputs, schema)
        cassette_path = self.cassette_dir / f"{cassette_key}.json"
        cassette_data = {
            "data": response.data,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
                "cost_usd": response.usage.cost_usd,
                "model": response.usage.model,
                "provider": response.usage.provider,
            },
            "raw_response": response.raw_response,
            "prompt_id": response.prompt_id,
            "prompt_version": response.prompt_version,
            "model": response.model,
            "temperature": response.temperature,
            "created_at": response.created_at.isoformat(),
        }
        with open(cassette_path, "w") as handle:
            json.dump(cassette_data, handle, indent=2)

    def _cassette_key(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        schema: dict[str, Any],
    ) -> str:
        key_data = {"prompt_id": prompt_id, "inputs": inputs, "schema": schema}
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]
        return f"{prompt_id}_{key_hash}"

    def reset_cost_tracking(self) -> None:
        self.total_cost = 0.0


def _load_sidecar(settings_path: Optional[Path]) -> dict[str, Any]:
    path = settings_path
    if path is None:
        env_path = os.getenv("STAGECOACH_LLM_SETTINGS_PATH", "").strip()
        path = Path(env_path) if env_path else None
    if path is None or not Path(path).is_file():
        return {}
    try:
        return normalize_settings(json.loads(Path(path).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
