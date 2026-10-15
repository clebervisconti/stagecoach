"""xAI (Grok) adapter — OpenAI-compatible, owner-chosen default (ADR-007 / ADR-038)."""

from __future__ import annotations

from typing import Any

from .openai_compat import OpenAICompatibleProvider


class XAIProvider(OpenAICompatibleProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        models: dict[str, Any],
        timeout: int,
        retry_config: dict[str, int],
        transport=None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            models=models,
            timeout=timeout,
            retry_config=retry_config,
            provider_id="xai",
            transport=transport,
        )
