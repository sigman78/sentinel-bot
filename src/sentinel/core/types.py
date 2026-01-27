"""
Shared type definitions.

Core data structures used across modules.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class ContentType(Enum):
    TEXT = "text"
    VOICE = "voice"
    IMAGE = "image"
    FILE = "file"
    REACTION = "reaction"


class AgentType(Enum):
    DIALOG = "dialog"
    SLEEP = "sleep"
    AWARENESS = "awareness"
    CODE = "code"
    RESEARCH = "research"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Message:
    """Universal message format across interfaces."""

    id: str
    timestamp: datetime
    role: str  # "user" | "assistant" | "system"
    content: str
    content_type: ContentType = ContentType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_llm_format(self) -> dict[str, str]:
        """Convert to LLM API message format."""
        return {"role": self.role, "content": self.content}


@dataclass
class AgentContext:
    """Runtime context for an agent."""

    agent_id: str
    agent_type: AgentType
    conversation: list[Message] = field(default_factory=list)
    memories: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Action:
    """Represents an action an agent wants to take."""

    type: str
    target: str
    parameters: dict[str, Any]
    risk_level: RiskLevel = RiskLevel.LOW
    reversible: bool = True
    requires_approval: bool = False


@dataclass
class ActionResult:
    """Result of an executed action."""

    success: bool
    data: Any = None
    error: str | None = None
