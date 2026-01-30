"""Awareness agent - proactive monitoring and notifications."""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from sentinel.agents.base import AgentConfig, AgentState, BaseAgent, LLMProvider
from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType, ContentType, Message
from sentinel.memory.base import MemoryStore

logger = get_logger("agents.awareness")


@dataclass
class Reminder:
    """A scheduled reminder."""

    id: str
    message: str
    trigger_at: datetime
    recurring: timedelta | None = None
    notified: bool = False


@dataclass
class Monitor:
    """A condition to monitor."""

    id: str
    name: str
    check_fn: Callable[[], bool]
    message: str
    interval: timedelta = field(default_factory=lambda: timedelta(minutes=5))
    last_check: datetime | None = None
    triggered: bool = False


class AwarenessAgent(BaseAgent):
    """Background agent for proactive checks and notifications."""

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryStore,
        notify_callback: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        config = AgentConfig(
            agent_type=AgentType.AWARENESS,
            system_prompt="Proactive awareness agent",
        )
        super().__init__(config, llm, memory)
        self._reminders: dict[str, Reminder] = {}
        self._monitors: dict[str, Monitor] = {}
        self._notify_callback = notify_callback
        self._pending_notifications: list[str] = []

    async def process(self, message: Message) -> Message:
        """Parse natural language to create reminders."""
        # Simple passthrough for now - could parse "remind me" messages
        return Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content="Awareness agent processes reminders and monitors.",
            content_type=ContentType.TEXT,
        )

    def add_reminder(
        self,
        message: str,
        trigger_at: datetime,
        recurring: timedelta | None = None,
    ) -> str:
        """Add a reminder."""
        reminder_id = str(uuid4())[:8]
        self._reminders[reminder_id] = Reminder(
            id=reminder_id,
            message=message,
            trigger_at=trigger_at,
            recurring=recurring,
        )
        logger.info(f"Added reminder {reminder_id}: {message} at {trigger_at}")
        return reminder_id

    def remove_reminder(self, reminder_id: str) -> bool:
        """Remove a reminder."""
        if reminder_id in self._reminders:
            del self._reminders[reminder_id]
            return True
        return False

    def add_monitor(
        self,
        name: str,
        check_fn: Callable[[], bool],
        message: str,
        interval: timedelta | None = None,
    ) -> str:
        """Add a condition monitor."""
        monitor_id = str(uuid4())[:8]
        self._monitors[monitor_id] = Monitor(
            id=monitor_id,
            name=name,
            check_fn=check_fn,
            message=message,
            interval=interval or timedelta(minutes=5),
        )
        logger.info(f"Added monitor {monitor_id}: {name}")
        return monitor_id

    def remove_monitor(self, monitor_id: str) -> bool:
        """Remove a monitor."""
        if monitor_id in self._monitors:
            del self._monitors[monitor_id]
            return True
        return False

    async def check_all(self) -> list[str]:
        """Check all reminders and monitors, return notifications."""
        self.state = AgentState.ACTIVE
        notifications: list[str] = []
        now = datetime.now()

        # Check reminders
        for reminder in list(self._reminders.values()):
            if not reminder.notified and reminder.trigger_at <= now:
                notifications.append(f"Reminder: {reminder.message}")
                reminder.notified = True

                if reminder.recurring:
                    # Schedule next occurrence
                    reminder.trigger_at = now + reminder.recurring
                    reminder.notified = False
                else:
                    # One-shot, remove it
                    del self._reminders[reminder.id]

        # Check monitors
        for monitor in self._monitors.values():
            if monitor.last_check and now - monitor.last_check < monitor.interval:
                continue

            monitor.last_check = now
            try:
                if monitor.check_fn() and not monitor.triggered:
                    notifications.append(f"Alert [{monitor.name}]: {monitor.message}")
                    monitor.triggered = True
                elif not monitor.check_fn():
                    monitor.triggered = False  # Reset when condition clears
            except Exception as e:
                logger.warning(f"Monitor {monitor.name} check failed: {e}")

        # Send notifications
        for msg in notifications:
            await self._notify(msg)

        self.state = AgentState.READY
        return notifications

    async def _notify(self, message: str) -> None:
        """Send notification via callback or queue for later."""
        if self._notify_callback:
            try:
                result = self._notify_callback(message)
                if inspect.isawaitable(result):
                    await result
            except Exception as e:
                logger.warning(f"Notification callback failed: {e}")
                self._pending_notifications.append(message)
        else:
            self._pending_notifications.append(message)

    def get_pending_notifications(self) -> list[str]:
        """Get and clear pending notifications."""
        pending = self._pending_notifications.copy()
        self._pending_notifications.clear()
        return pending

    def list_reminders(self) -> list[dict[str, Any]]:
        """List all active reminders."""
        return [
            {
                "id": r.id,
                "message": r.message,
                "trigger_at": r.trigger_at.isoformat(),
                "recurring": str(r.recurring) if r.recurring else None,
            }
            for r in self._reminders.values()
        ]

    def list_monitors(self) -> list[dict[str, Any]]:
        """List all active monitors."""
        return [
            {"id": m.id, "name": m.name, "interval": str(m.interval)}
            for m in self._monitors.values()
        ]
