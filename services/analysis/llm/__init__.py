"""LLM Client Package for Stage Coach

Provider-neutral LLM client with structured output support.
Per ADR-007 / ADR-060: local LM Studio (Qwen) is the default; xAI stays selectable.
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
