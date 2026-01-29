"""
LLM provider interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentinel.llm.router import TaskType


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
    tool_calls: list[dict] | None = None  # Native tool calls from API


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
        messages: list[dict],
        config: LLMConfig,
        task: "TaskType | None" = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """
        Generate completion from messages.

        Supports both text-only and multimodal (vision) messages.

        Args:
            messages: Conversation messages (can include images)
            config: LLM configuration
            task: Task type for routing
            tools: Tool definitions in provider-specific format (optional)

        Returns:
            LLMResponse with content and optional tool_calls
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        ...
