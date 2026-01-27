"""
LLM provider interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class ProviderType(Enum):
    CLAUDE = "claude"
    OPENROUTER = "openrouter"
    LOCAL = "local"


@dataclass
class LLMResponse:
    """Response from LLM provider."""

    content: str
    model: str
    provider: ProviderType
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict | None = None


@dataclass
class LLMConfig:
    """Configuration for LLM call."""

    model: str
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: str | None = None


class LLMProvider(ABC):
    """Abstract LLM provider."""

    provider_type: ProviderType

    @abstractmethod
    async def complete(
        self,
        messages: list[dict[str, str]],
        config: LLMConfig,
    ) -> LLMResponse:
        """Generate completion from messages."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        ...
