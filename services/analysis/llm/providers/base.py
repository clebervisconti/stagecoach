"""Base LLM Provider Interface"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..client import LLMResponse, UsageStats


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""

    @abstractmethod
    def generate_structured(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
        model: str,
        temperature: Optional[float] = None,
    ) -> LLMResponse:
        """
        Generate structured output conforming to schema.

        Args:
            prompt_id: Prompt identifier
            inputs: Template inputs
            schema: JSON Schema for output
            model: Model identifier
            temperature: Sampling temperature

        Returns:
            LLMResponse with validated structured data

        Raises:
            LLMError and subclasses
        """
        pass
