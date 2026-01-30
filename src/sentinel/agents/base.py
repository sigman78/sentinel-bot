"""
Base agent interface.

All agents inherit from BaseAgent and implement the process method.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from sentinel.core.types import AgentContext, AgentType, Message
from sentinel.core.typing import MessageDict, ToolSpec

if TYPE_CHECKING:
    from sentinel.llm.base import LLMConfig, LLMResponse
    from sentinel.memory.base import MemoryStore


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for LLM providers (router or direct provider)."""

    async def complete(
        self,
        messages: list[MessageDict],
        config: "LLMConfig",
        preferred: str | None = None,
        task: object = None,
        tools: list[ToolSpec] | None = None,
    ) -> "LLMResponse":
        """Generate completion from messages."""
        ...


class AgentState(Enum):
    INIT = "init"
    READY = "ready"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


@dataclass
class AgentConfig:
    """Agent-specific configuration."""

    agent_type: AgentType
    system_prompt: str
    max_turns: int = 10
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base for all agents."""

    def __init__(
        self,
        config: AgentConfig,
        llm: "LLMProvider",
        memory: "MemoryStore | None",
    ):
        self.config = config
        self.llm = llm
        self.memory = memory
        self.state = AgentState.INIT
        self.context = AgentContext(
            agent_id=f"{config.agent_type.value}_{datetime.now().timestamp()}",
            agent_type=config.agent_type,
        )

    @abstractmethod
    async def process(self, message: Message) -> Message:
        """Process input message, return response."""
        ...

    async def initialize(self) -> None:
        """Load memories and prepare context."""
        self.state = AgentState.READY

    async def terminate(self) -> None:
        """Clean up resources."""
        self.state = AgentState.TERMINATED

    def _build_messages(self) -> list[MessageDict]:
        """Build message list for LLM call."""
        messages = [{"role": "system", "content": self.config.system_prompt}]
        for msg in self.context.conversation:
            messages.append(msg.to_llm_format())
        return messages
