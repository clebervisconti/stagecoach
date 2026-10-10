"""Shared types for LLM client and providers."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


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
