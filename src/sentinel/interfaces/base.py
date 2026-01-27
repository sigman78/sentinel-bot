"""
Interface protocol and common types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from sentinel.core.types import ContentType


class InterfaceType(Enum):
    TELEGRAM = "telegram"
    CLI = "cli"
    API = "api"


@dataclass
class InboundMessage:
    """Message received from interface."""

    id: str
    timestamp: datetime
    source: InterfaceType
    content: str | bytes
    content_type: ContentType = ContentType.TEXT
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutboundMessage:
    """Message to send via interface."""

    content: str
    format: str = "markdown"  # plain, markdown, html
    reply_to: str | None = None
    attachments: list[Any] = field(default_factory=list)


class Interface(ABC):
    """Abstract interface adapter."""

    @abstractmethod
    async def receive(self) -> InboundMessage:
        """Receive next message from interface."""
        ...

    @abstractmethod
    async def send(self, message: OutboundMessage) -> None:
        """Send message to interface."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start interface listener."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop interface listener."""
        ...
