"""
Memory store interface and implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sentinel.memory.profile import UserProfile


class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROFILE = "profile"
    WORLD = "world"


@dataclass
class MemoryEntry:
    """Single memory record."""

    id: str
    type: MemoryType
    content: str
    timestamp: datetime
    importance: float = 0.5  # 0-1 ranking
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class MemoryStore(ABC):
    """Abstract memory storage interface."""

    @abstractmethod
    async def store(self, entry: MemoryEntry) -> str:
        """Store memory, return ID."""
        ...

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories."""
        ...

    @abstractmethod
    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Get specific memory by ID."""
        ...

    @abstractmethod
    async def update(self, memory_id: str, **fields: Any) -> bool:
        """Update memory fields."""
        ...

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """Delete memory."""
        ...

    # User profile operations (optional - not all stores need profiles)
    async def get_profile(self) -> "UserProfile | None":
        """Get user profile. Returns None if not implemented."""
        return None

    async def update_profile(self, profile: "UserProfile") -> None:
        """Update user profile. No-op if not implemented."""
        return None
