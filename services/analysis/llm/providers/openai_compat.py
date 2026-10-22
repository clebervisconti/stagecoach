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
        local = self.provider_id == "local"
        if local:
            user_content = _local_user_prompt(prompt_id, inputs, schema)
        else:
            user_content = _user_prompt(prompt_id, inputs)
        request_data = {
            "model": model,
            "messages": [
                {"role": "system", "content": _system_prompt(no_think=local)},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
        }
        if local:
            # Qwen 3.8 defaults to maximum thinking. The OpenAI-compatible endpoint
            # ignores a request to turn it off, so the native chat API is used.
            request_data["max_tokens"] = min(int(model_config.get("max_tokens") or 4096), 4096)
        else:
            request_data["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{prompt_id}_response",
                    "strict": True,
                    "schema": schema,
                },
            }
        last_error: Exception | None = None
        attempts = 1 if local else self.retry_config.get("max_attempts", 1)
        for attempt in range(attempts):
            try:
                response = self._post_native(request_data) if local else self._post(request_data)
                message = response["choices"][0]["message"]
                content = message.get("content") or ""
                if not content.strip() and not local:
                    plain = {key: value for key, value in request_data.items() if key != "response_format"}
                    response = self._post(plain)
                    message = response["choices"][0]["message"]
                    content = message.get("content") or ""
                if not content.strip():
                    content = message.get("reasoning_content") or ""
                data = _parse_json_object(content)
                if local and _looks_like_schema_document(data):
                    request_data["messages"][1]["content"] = _instance_only_prompt(prompt_id, inputs, schema)
                    response = self._post_native(request_data)
                    message = response["choices"][0]["message"]
                    content = message.get("content") or message.get("reasoning_content") or ""
                    data = _parse_json_object(content)
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
                if attempt < attempts - 1:
                    time.sleep(self.retry_config.get("backoff_factor", 2) ** attempt)
                    continue
                raise
        raise last_error or LLMError("Request failed after retries")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _post(self, request_data: dict[str, Any]) -> dict[str, Any]:
        return self.transport.post(
            f"{self.base_url}/chat/completions",
            self._headers(),
            request_data,
            self.timeout,
        )

    def _native_chat_url(self) -> str:
        root = self.base_url.rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        return root + "/api/v1/chat"

    def _post_native(self, request_data: dict[str, Any]) -> dict[str, Any]:
        body = {
            "model": request_data["model"],
            "input": request_data["messages"][1]["content"],
            "system_prompt": request_data["messages"][0]["content"],
            "temperature": min(float(request_data["temperature"]), 1.0),
            "max_output_tokens": int(request_data.get("max_tokens") or 4096),
            "reasoning": "off",
            "stream": False,
            "store": False,
        }
        raw = self.transport.post(self._native_chat_url(), self._headers(), body, self.timeout)
        return _openai_shape_from_native(raw)


def _openai_shape_from_native(raw: dict[str, Any]) -> dict[str, Any]:
    if "choices" in raw:
        return raw
    messages: list[str] = []
    reasoning: list[str] = []
    for item in raw.get("output") or []:
        if item.get("type") == "message":
            messages.append(item.get("content") or "")
        elif item.get("type") == "reasoning":
            reasoning.append(item.get("content") or "")
    stats = raw.get("stats") or {}
    prompt_tokens = int(stats.get("input_tokens") or 0)
    completion_tokens = int(stats.get("total_output_tokens") or 0)
    return {
        "choices": [
            {
                "message": {
                    "content": "\n".join(messages),
                    "reasoning_content": "\n".join(reasoning),
                }
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _parse_json_object(content: str) -> Any:
    text = (content or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        raise


def _system_prompt(no_think: bool = False) -> str:
    text = (
        "You are a presentation-evaluation assistant. "
        "Evaluate ONLY the transcript provided. "
        "Quote exactly (verbatim, original language). "
        "Do not judge accent or native-likeness. "
        "Do not infer the speaker's emotions."
    )
    if no_think:
        return (
            text
            + " Reply with JSON only. Do not repeat the transcript. Do not think out loud."
            + " /no_think"
        )
    return text


def _looks_like_schema_document(data: Any) -> bool:
    return isinstance(data, dict) and ("$schema" in data or ("properties" in data and "required" in data))


def _local_user_prompt(prompt_id: str, inputs: dict[str, Any], schema: dict[str, Any]) -> str:
    parts = [
        f"Return one JSON object for {prompt_id}.",
        "The object must be an instance of the schema, not a copy of the schema.",
        "Do not repeat the transcript.",
    ]
    for key, value in inputs.items():
        if key == "transcript" and isinstance(value, str):
            parts.append("Transcript:\n" + value)
        else:
            parts.append(f"{key}: {value if isinstance(value, str) else json.dumps(value)}")
    parts.append("Schema:\n" + json.dumps(schema))
    return "\n\n".join(parts)


def _instance_only_prompt(prompt_id: str, inputs: dict[str, Any], schema: dict[str, Any]) -> str:
    keys = ", ".join(str(item) for item in (schema.get("required") or []))
    parts = [
        f"Return one JSON object for {prompt_id} with keys: {keys}.",
        "Do not return a JSON schema.",
    ]
    transcript = inputs.get("transcript")
    if isinstance(transcript, str) and transcript:
        parts.append("Transcript:\n" + transcript)
    return "\n\n".join(parts)


def _user_prompt(prompt_id: str, inputs: dict[str, Any]) -> str:
    return f"Prompt: {prompt_id}\n\nInputs:\n{json.dumps(inputs, indent=2)}"
