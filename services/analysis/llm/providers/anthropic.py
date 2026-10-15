"""Anthropic Claude Messages API adapter. Tests inject a stand-in transport."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate

from ..exceptions import LLMError, LLMRateLimitError, LLMTimeoutError, LLMValidationError
from ..transport import HttpTransport, RequestsTransport
from ..types import LLMResponse, UsageStats
from .base import BaseLLMProvider
from .openai_compat import _system_prompt, _user_prompt


class AnthropicProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        models: dict[str, Any],
        timeout: int,
        retry_config: dict[str, int],
        transport: HttpTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.timeout = timeout
        self.retry_config = retry_config
        self.transport = transport or RequestsTransport()

    def generate_structured(
        self,
        prompt_id: str,
        inputs: dict[str, Any],
        schema: dict[str, Any],
        model: str,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        model_config = self.models.get(model) or {
            "temperature_default": 0.4,
            "price_per_input_token": 0.0,
            "price_per_output_token": 0.0,
        }
        if temperature is None:
            temperature = model_config.get("temperature_default", 0.4)
        request_data = {
            "model": model,
            "max_tokens": 4096,
            "temperature": temperature,
            "system": _system_prompt(),
            "messages": [{"role": "user", "content": _user_prompt(prompt_id, inputs)}],
            "output_format": {"type": "json_schema", "schema": schema},
        }
        last_error: Exception | None = None
        for attempt in range(self.retry_config.get("max_attempts", 1)):
            try:
                response = self._post(request_data)
                data = _extract_json(response)
                try:
                    validate(instance=data, schema=schema)
                except JSONSchemaValidationError as exc:
                    raise LLMValidationError(f"Response failed schema validation: {exc.message}") from exc
                usage_data = response.get("usage") or {}
                prompt_tokens = int(usage_data.get("input_tokens") or usage_data.get("prompt_tokens") or 0)
                completion_tokens = int(usage_data.get("output_tokens") or usage_data.get("completion_tokens") or 0)
                cost_usd = (
                    prompt_tokens * float(model_config.get("price_per_input_token") or 0)
                    + completion_tokens * float(model_config.get("price_per_output_token") or 0)
                )
                return LLMResponse(
                    data=data,
                    usage=UsageStats(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                        cost_usd=cost_usd,
                        model=model,
                        provider="anthropic",
                    ),
                    raw_response=response,
                    prompt_id=prompt_id,
                    prompt_version="1.0.0",
                    model=model,
                    temperature=float(temperature),
                )
            except (LLMRateLimitError, LLMTimeoutError) as exc:
                last_error = exc
                if attempt < self.retry_config.get("max_attempts", 1) - 1:
                    time.sleep(self.retry_config.get("backoff_factor", 2) ** attempt)
                    continue
                raise
        raise last_error or LLMError("Request failed after retries")

    def _post(self, request_data: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        return self.transport.post(
            f"{self.base_url}/v1/messages",
            headers,
            request_data,
            self.timeout,
        )


def _extract_json(response: dict[str, Any]) -> dict[str, Any]:
    if isinstance(response.get("data"), dict):
        return response["data"]
    content = response.get("content") or []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"text", "output_json"}:
                text = block.get("text") or block.get("json")
                if isinstance(text, dict):
                    return text
                if isinstance(text, str):
                    return json.loads(text)
    raise LLMValidationError("Anthropic response had no JSON content")
