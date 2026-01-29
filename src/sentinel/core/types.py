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

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to LLM API message format.

        Supports multimodal content (text + images) for vision-capable models.
        """
        # Simple text message
        if self.content_type == ContentType.TEXT and "images" not in self.metadata:
            return {"role": self.role, "content": self.content}

        # Multimodal message (text + images)
        if "images" in self.metadata:
            content_blocks = []

            # Add text block if present
            if self.content:
                content_blocks.append({
                    "type": "text",
                    "text": self.content
                })

            # Add image blocks
            for img in self.metadata["images"]:
                content_blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": img.get("media_type", "image/jpeg"),
                        "data": img["data"]  # Base64 encoded
                    }
                })

            return {"role": self.role, "content": content_blocks}

        # Fallback
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
