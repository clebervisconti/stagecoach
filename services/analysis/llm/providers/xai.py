"""xAI (Grok) LLM Provider

Per ADR-007: First provider implementation with strict JSON schema structured outputs.
"""

import json
import time
from typing import Any, Dict, Optional

import requests
from jsonschema import validate, ValidationError as JSONSchemaValidationError

from ..client import LLMResponse, UsageStats
from ..exceptions import (
    LLMAuthError,
    LLMError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMValidationError,
)
from .base import BaseLLMProvider


class XAIProvider(BaseLLMProvider):
    """
    xAI (Grok) provider implementation.

    Implements OpenAI-compatible API with structured outputs.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        models: Dict[str, Any],
        timeout: int,
        retry_config: Dict[str, int],
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.models = models
        self.timeout = timeout
        self.retry_config = retry_config

    def generate_structured(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
        model: str,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """Generate structured output via xAI API"""
        # Get model config
        if model not in self.models:
            raise ValueError(f"Model {model} not configured for xai provider")

        model_config = self.models[model]

        # Resolve temperature
        if temperature is None:
            temperature = model_config["temperature_default"]

        # Build prompt (simple template for now, will be replaced with actual prompts)
        system_prompt = self._build_system_prompt(prompt_id)
        user_prompt = self._build_user_prompt(prompt_id, inputs)

        # Prepare API request with structured output
        request_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
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

        # Retry loop
        last_error = None
        for attempt in range(self.retry_config["max_attempts"]):
            try:
                response = self._make_request(request_data)

                # Extract structured data
                content = response["choices"][0]["message"]["content"]
                data = json.loads(content)

                # Validate against schema
                try:
                    validate(instance=data, schema=schema)
                except JSONSchemaValidationError as e:
                    raise LLMValidationError(
                        f"Response failed schema validation: {e.message}"
                    )

                # Calculate cost
                usage_data = response["usage"]
                cost_usd = self._calculate_cost(
                    usage_data["prompt_tokens"],
                    usage_data["completion_tokens"],
                    model_config,
                )

                # Build response
                return LLMResponse(
                    data=data,
                    usage=UsageStats(
                        prompt_tokens=usage_data["prompt_tokens"],
                        completion_tokens=usage_data["completion_tokens"],
                        total_tokens=usage_data["total_tokens"],
                        cost_usd=cost_usd,
                        model=model,
                        provider="xai",
                    ),
                    raw_response=response,
                    prompt_id=prompt_id,
                    prompt_version="1.0.0",  # TODO: get from prompt metadata
                    model=model,
                    temperature=temperature,
                )

            except (LLMRateLimitError, LLMTimeoutError) as e:
                last_error = e
                if attempt < self.retry_config["max_attempts"] - 1:
                    backoff = (
                        self.retry_config["backoff_factor"] ** attempt
                    )
                    time.sleep(backoff)
                    continue
                else:
                    raise

            except (LLMAuthError, LLMValidationError, LLMError):
                # Don't retry these
                raise

        # If we get here, we exhausted retries
        raise last_error or LLMError("Request failed after retries")

    def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request with error handling"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=request_data,
                timeout=self.timeout,
            )

            if response.status_code == 401:
                raise LLMAuthError("Invalid API key")
            elif response.status_code == 429:
                raise LLMRateLimitError("Rate limit exceeded")
            elif response.status_code >= 500:
                raise LLMError(f"Server error: {response.status_code}")
            elif response.status_code != 200:
                raise LLMError(
                    f"API error {response.status_code}: {response.text}"
                )

            return response.json()

        except requests.Timeout:
            raise LLMTimeoutError("Request timed out")
        except requests.RequestException as e:
            raise LLMError(f"Request failed: {e}")

    def _calculate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model_config: Dict[str, Any],
    ) -> float:
        """Calculate cost in USD"""
        input_cost = (
            prompt_tokens * model_config["price_per_input_token"]
        )
        output_cost = (
            completion_tokens * model_config["price_per_output_token"]
        )
        return input_cost + output_cost

    def _build_system_prompt(self, prompt_id: str) -> str:
        """Build system prompt (placeholder for now)"""
        return (
            "You are a presentation-evaluation assistant. "
            "Evaluate ONLY the transcript provided. "
            "Quote exactly (verbatim, original language). "
            "Do not judge accent or native-likeness. "
            "Do not infer the speaker's emotions."
        )

    def _build_user_prompt(
        self, prompt_id: str, inputs: Dict[str, Any]
    ) -> str:
        """Build user prompt (placeholder for now)"""
        # TODO: Load actual prompt templates from prompts/ directory
        # For now, just serialize inputs as JSON
        return (
            f"Prompt: {prompt_id}\n\n"
            f"Inputs:\n{json.dumps(inputs, indent=2)}"
        )
