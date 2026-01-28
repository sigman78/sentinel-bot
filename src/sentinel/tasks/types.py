"""Task type definitions."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TaskType(Enum):
    """Types of scheduled tasks."""

    REMINDER = "reminder"  # Simple notification
    AGENT_TASK = "agent_task"  # Delegate to agent, send result
    API_CALL = "api_call"  # HTTP request
    WEB_SEARCH = "web_search"  # Search + summarize


@dataclass
class ScheduledTask:
    """A scheduled task with execution parameters."""

    id: str
    task_type: TaskType
    description: str
    schedule_type: str  # 'once' | 'recurring'
    schedule_data: dict  # {"delay": "5m"} | {"pattern": "daily", "time": "09:00"}
    execution_data: dict | None
    enabled: bool
    created_at: datetime
    last_run: datetime | None
    next_run: datetime

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        return {
            "id": self.id,
            "task_type": self.task_type.value,
            "description": self.description,
            "schedule_type": self.schedule_type,
            "schedule_data": self.schedule_data,
            "execution_data": self.execution_data,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat(),
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ScheduledTask":
        """Create from dict loaded from storage."""
        return cls(
            id=data["id"],
            task_type=TaskType(data["task_type"]),
            description=data["description"],
            schedule_type=data["schedule_type"],
            schedule_data=data["schedule_data"],
            execution_data=data.get("execution_data"),
            enabled=bool(data["enabled"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_run=datetime.fromisoformat(data["last_run"]) if data.get("last_run") else None,
            next_run=datetime.fromisoformat(data["next_run"]),
        )
