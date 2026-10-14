"""LLM Client Package for Stage Coach

Provider-neutral LLM client with structured output support.
Per ADR-007: xAI (Grok) as the first provider.
"""

from .client import LLMClient
from .types import LLMResponse, UsageStats
from .exceptions import (
    LLMError,
    LLMAuthError,
    LLMRateLimitError,
    LLMTimeoutError,
    LLMCostExceededError,
    LLMValidationError,
)

__all__ = [
    "LLMClient",
    "LLMResponse",
    "UsageStats",
    "LLMError",
    "LLMAuthError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "LLMCostExceededError",
    "LLMValidationError",
]
