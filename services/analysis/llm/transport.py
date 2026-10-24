"""HTTP transport for LLM providers. Tests inject a stand-in — no live calls."""

from __future__ import annotations

from typing import Any, Protocol

from .exceptions import LLMAuthError, LLMError, LLMRateLimitError, LLMTimeoutError


class HttpTransport(Protocol):
    def post(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]: ...


class RequestsTransport:
    """Production transport. Not used by unit tests."""

    def post(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        import requests

        try:
            response = requests.post(
                url, headers=headers, json=json_body, timeout=_timeout_pair(timeout)
            )
        except requests.Timeout as exc:
            raise LLMTimeoutError("Request timed out") from exc
        except requests.RequestException as exc:
            raise LLMError(f"Request failed: {exc}") from exc
        return _response_json(response)

    def post_stream(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: int,
    ):
        """Yield response lines. ``timeout`` is the read gap, not the whole completion."""
        import requests

        try:
            response = requests.post(
                url,
                headers=headers,
                json=json_body,
                timeout=_timeout_pair(timeout),
                stream=True,
            )
        except requests.Timeout as exc:
            raise LLMTimeoutError("Request timed out") from exc
        except requests.RequestException as exc:
            raise LLMError(f"Request failed: {exc}") from exc
        try:
            _raise_for_status(response)
            for raw in response.iter_lines(decode_unicode=True):
                if raw:
                    yield raw
        except requests.Timeout as exc:
            raise LLMTimeoutError("Request timed out") from exc
        finally:
            response.close()


def _timeout_pair(timeout: int) -> tuple[int, int]:
    read = max(1, int(timeout))
    return min(10, read), read


def _raise_for_status(response: Any) -> None:
    if response.status_code == 401:
        raise LLMAuthError("Invalid API key")
    if response.status_code == 429:
        raise LLMRateLimitError("Rate limit exceeded")
    if response.status_code >= 500:
        raise LLMError(f"Server error: {response.status_code}")
    if response.status_code != 200:
        raise LLMError(f"API error {response.status_code}: {response.text[:200]}")


def _response_json(response: Any) -> dict[str, Any]:
    _raise_for_status(response)
    return response.json()


class StandinTransport:
    """In-memory stand-in. Records calls; never opens a socket."""

    def __init__(self, payload: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.payload = payload or {}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: int,
    ) -> dict[str, Any]:
        redacted = {k: ("<redacted>" if "authorization" in k.lower() or "api-key" in k.lower() else v) for k, v in headers.items()}
        self.calls.append({"url": url, "headers": redacted, "json": json_body, "timeout": timeout})
        if self.error:
            raise self.error
        return self.payload
