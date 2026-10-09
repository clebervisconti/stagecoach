"""LLM-specific exceptions per ADR-007"""


class LLMError(Exception):
    """Base exception for LLM errors"""

    pass


class LLMAuthError(LLMError):
    """API key invalid or missing"""

    pass


class LLMRateLimitError(LLMError):
    """Rate limit exceeded"""

    pass


class LLMTimeoutError(LLMError):
    """Request timed out"""

    pass


class LLMCostExceededError(LLMError):
    """Cost ceiling exceeded"""

    pass


class LLMValidationError(LLMError):
    """Response failed schema validation"""

    pass
