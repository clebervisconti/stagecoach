"""OpenAI-compatible chat completions (xAI, OpenAI, Gemini, local, custom)."""

from __future__ import annotations

import json
import time
from typing import Any, Optional

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate

from ..catalog import normalize_provider_id
from ..exceptions import LLMError, LLMRateLimitError, LLMTimeoutError, LLMValidationError
from ..transport import HttpTransport, RequestsTransport
from ..types import LLMResponse, UsageStats
from .base import BaseLLMProvider


class OpenAICompatibleProvider(BaseLLMProvider):
    """POST /chat/completions with json_schema structured outputs."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        models: dict[str, Any],
        timeout: int,
        retry_config: dict[str, int],
        provider_id: str = "openai",
        transport: HttpTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.timeout = timeout
        self.retry_config = retry_config
        self.provider_id = normalize_provider_id(provider_id)
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
            "messages": [
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(prompt_id, inputs)},
            ],
            "temperature": temperature,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{prompt_id}_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        }
        last_error: Exception | None = None
        for attempt in range(self.retry_config.get("max_attempts", 1)):
            try:
                response = self._post(request_data)
                content = response["choices"][0]["message"]["content"]
                data = json.loads(content)
                try:
                    validate(instance=data, schema=schema)
                except JSONSchemaValidationError as exc:
                    raise LLMValidationError(f"Response failed schema validation: {exc.message}") from exc
                usage_data = response.get("usage") or {}
                prompt_tokens = int(usage_data.get("prompt_tokens") or 0)
                completion_tokens = int(usage_data.get("completion_tokens") or 0)
                cost_usd = (
                    prompt_tokens * float(model_config.get("price_per_input_token") or 0)
                    + completion_tokens * float(model_config.get("price_per_output_token") or 0)
                )
                return LLMResponse(
                    data=data,
                    usage=UsageStats(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=int(usage_data.get("total_tokens") or (prompt_tokens + completion_tokens)),
                        cost_usd=cost_usd,
                        model=model,
                        provider=self.provider_id,
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
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        return self.transport.post(
            f"{self.base_url}/chat/completions",
            headers,
            request_data,
            self.timeout,
        )


def _system_prompt() -> str:
    return (
        "You are a presentation-evaluation assistant. "
        "Evaluate ONLY the transcript provided. "
        "Quote exactly (verbatim, original language). "
        "Do not judge accent or native-likeness. "
        "Do not infer the speaker's emotions."
    )


def _user_prompt(prompt_id: str, inputs: dict[str, Any]) -> str:
    return f"Prompt: {prompt_id}\n\nInputs:\n{json.dumps(inputs, indent=2)}"
