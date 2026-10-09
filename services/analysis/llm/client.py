"""LLM Client: Provider-neutral interface for structured LLM calls

Per ADR-007: Clean interface, provider adapters, cost tracking, cassettes.
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, ValidationError

from .exceptions import (
    LLMAuthError,
    LLMCostExceededError,
    LLMValidationError,
)
from .providers.base import BaseLLMProvider
from .providers.xai import XAIProvider


@dataclass
class UsageStats:
    """Token usage and cost statistics"""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    model: str
    provider: str


@dataclass
class LLMResponse:
    """LLM response with structured data and metadata"""

    data: Dict[str, Any]  # Validated against schema
    usage: UsageStats
    raw_response: Dict[str, Any] = field(repr=False)  # Full API response
    prompt_id: str = ""
    prompt_version: str = ""
    model: str = ""
    temperature: float = 0.4
    created_at: datetime = field(default_factory=datetime.utcnow)


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
        # response.data is validated against schema
        # response.usage contains token counts and cost
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        api_key: Optional[str] = None,
        provider_name: Optional[str] = None,
        use_cassettes: Optional[bool] = None,
    ):
        """
        Initialize LLM client.

        Args:
            config_path: Path to llm.yaml config (default: services/analysis/config/llm.yaml)
            api_key: API key (default: from LLM_API_KEY env var)
            provider_name: Override provider (default: from config or LLM_PROVIDER env var)
            use_cassettes: Override cassette setting (default: from config)
        """
        # Load config
        if config_path is None:
            config_path = (
                Path(__file__).parent.parent / "config" / "llm.yaml"
            )
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # Resolve provider
        self.provider_name = (
            provider_name
            or os.getenv("LLM_PROVIDER")
            or self.config["default_provider"]
        )
        if self.provider_name not in self.config["providers"]:
            raise ValueError(
                f"Provider {self.provider_name} not found in config"
            )

        # Get API key
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        if not self.api_key:
            raise LLMAuthError(
                "LLM_API_KEY environment variable not set. "
                "Set it to enable live LLM calls, or use cassettes for testing."
            )

        # Initialize provider
        provider_config = self.config["providers"][self.provider_name]
        self.provider: BaseLLMProvider = self._create_provider(
            self.provider_name, provider_config
        )

        # Cassette settings
        self.use_cassettes = (
            use_cassettes
            if use_cassettes is not None
            else self.config["cassettes"]["enabled"]
        )
        self.cassette_dir = Path(self.config["cassettes"]["directory"])
        self.cassette_dir.mkdir(parents=True, exist_ok=True)

        # Cost tracking
        self.total_cost = 0.0
        self.cost_ceiling = self.config["cost_ceiling_per_analysis"]

    def _create_provider(
        self, provider_name: str, provider_config: Dict[str, Any]
    ) -> BaseLLMProvider:
        """Factory method to create provider instance"""
        if provider_name == "xai":
            return XAIProvider(
                api_key=self.api_key,
                base_url=provider_config["base_url"],
                models=provider_config["models"],
                timeout=self.config["timeout"]["default"],
                retry_config=self.config["retry"],
            )
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def generate_structured(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Generate structured output from LLM.

        Args:
            prompt_id: Prompt identifier (e.g., "message_v1")
            inputs: Template inputs (context, segments, etc.)
            schema: JSON Schema for output validation
            model: Override model (default: from config model_assignments)
            temperature: Override temperature

        Returns:
            LLMResponse with validated data and usage stats

        Raises:
            LLMCostExceededError: If cost ceiling would be exceeded
            LLMValidationError: If response doesn't match schema
            LLMError: For other provider errors
        """
        # Check cassette first if enabled
        if self.use_cassettes:
            cassette_response = self._try_load_cassette(
                prompt_id, inputs, schema
            )
            if cassette_response:
                return cassette_response

        # Check cost ceiling
        if self.total_cost >= self.cost_ceiling:
            raise LLMCostExceededError(
                f"Cost ceiling of ${self.cost_ceiling:.2f} exceeded "
                f"(current: ${self.total_cost:.4f})"
            )

        # Resolve model
        model = model or self.config["model_assignments"].get(
            prompt_id, self.config["model_assignments"]["default"]
        )

        # Call provider
        response = self.provider.generate_structured(
            prompt_id=prompt_id,
            inputs=inputs,
            schema=schema,
            model=model,
            temperature=temperature,
        )

        # Track cost
        self.total_cost += response.usage.cost_usd

        # Save cassette if enabled
        if self.use_cassettes:
            self._save_cassette(prompt_id, inputs, schema, response)

        return response

    def _try_load_cassette(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Optional[LLMResponse]:
        """Try to load response from cassette"""
        cassette_key = self._cassette_key(prompt_id, inputs, schema)
        cassette_path = self.cassette_dir / f"{cassette_key}.json"

        if not cassette_path.exists():
            return None

        with open(cassette_path) as f:
            cassette_data = json.load(f)

        # Reconstruct LLMResponse
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
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
        response: LLMResponse,
    ):
        """Save response to cassette"""
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

        with open(cassette_path, "w") as f:
            json.dump(cassette_data, f, indent=2)

    def _cassette_key(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> str:
        """Generate deterministic cassette key from inputs"""
        # Hash inputs and schema to create unique key
        key_data = {
            "prompt_id": prompt_id,
            "inputs": inputs,
            "schema": schema,
        }
        key_json = json.dumps(key_data, sort_keys=True)
        key_hash = hashlib.sha256(key_json.encode()).hexdigest()[:16]
        return f"{prompt_id}_{key_hash}"

    def reset_cost_tracking(self):
        """Reset cost tracking (call at start of each analysis)"""
        self.total_cost = 0.0
