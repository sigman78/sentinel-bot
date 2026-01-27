"""Agent orchestrator - manages agent lifecycles and background tasks."""

import asyncio
import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from sentinel.core.logging import get_logger
from sentinel.core.types import AgentType

logger = get_logger("core.orchestrator")


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3


@dataclass
class ScheduledTask:
    """A task scheduled for background execution."""

    id: str
    name: str
    callback: Callable
    interval: timedelta | None = None  # None = one-shot
    priority: TaskPriority = TaskPriority.NORMAL
    next_run: datetime = field(default_factory=datetime.now)
    last_run: datetime | None = None
    enabled: bool = True
    running: bool = False


class Orchestrator:
    """Manages agent lifecycles and schedules background tasks."""

    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}  # noqa: F821
        self._tasks: dict[str, ScheduledTask] = {}
        self._running = False
        self._scheduler_task: asyncio.Task | None = None
        self._idle_threshold = timedelta(minutes=5)
        self._last_activity: datetime = datetime.now()

    def register_agent(self, agent_id: str, agent: "BaseAgent") -> None:  # noqa: F821
        """Register an agent with the orchestrator."""
        self._agents[agent_id] = agent
        logger.debug(f"Registered agent: {agent_id}")

    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.debug(f"Unregistered agent: {agent_id}")

    def get_agent(self, agent_type: AgentType) -> "BaseAgent | None":  # noqa: F821
        """Get agent by type."""
        for agent in self._agents.values():
            if agent.config.agent_type == agent_type:
                return agent
        return None

    def schedule_task(
        self,
        task_id: str,
        name: str,
        callback: Callable,
        interval: timedelta | None = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        delay: timedelta | None = None,
    ) -> None:
        """Schedule a background task."""
        next_run = datetime.now()
        if delay:
            next_run += delay

        self._tasks[task_id] = ScheduledTask(
            id=task_id,
            name=name,
            callback=callback,
            interval=interval,
            priority=priority,
            next_run=next_run,
        )
        logger.info(f"Scheduled task: {name} (interval: {interval})")

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def mark_activity(self) -> None:
        """Mark user activity (resets idle timer)."""
        self._last_activity = datetime.now()

    def is_idle(self) -> bool:
        """Check if system has been idle past threshold."""
        return datetime.now() - self._last_activity > self._idle_threshold

    async def start(self) -> None:
        """Start the orchestrator scheduler."""
        if self._running:
            return
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Orchestrator started")

    async def stop(self) -> None:
        """Stop the orchestrator."""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._scheduler_task
        logger.info("Orchestrator stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - runs pending tasks."""
        while self._running:
            now = datetime.now()
            pending = [
                t for t in self._tasks.values()
                if t.enabled and not t.running and t.next_run <= now
            ]

            # Sort by priority (higher first)
            pending.sort(key=lambda t: t.priority.value, reverse=True)

            for task in pending:
                task.running = True
                try:
                    result = task.callback()
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Task {task.name} failed: {e}")
                finally:
                    task.running = False
                    task.last_run = datetime.now()

                    if task.interval:
                        task.next_run = datetime.now() + task.interval
                    else:
                        # One-shot task, remove it
                        del self._tasks[task.id]

            await asyncio.sleep(1)  # Check every second


# Singleton orchestrator instance
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
