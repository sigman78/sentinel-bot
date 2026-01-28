"""Task manager - coordinates task scheduling and execution."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from uuid import uuid4

from sentinel.core.logging import get_logger
from sentinel.core.types import ActionResult
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.executor import TaskExecutor
from sentinel.tasks.parser import ScheduleParser
from sentinel.tasks.types import ScheduledTask, TaskType

logger = get_logger("tasks.manager")


class TaskManager:
    """Manages scheduled tasks - creation, execution, and rescheduling."""

    def __init__(
        self,
        memory: SQLiteMemoryStore,
        notification_callback: Callable[[str], Awaitable[None]] | None = None,
    ):
        """
        Initialize task manager.

        Args:
            memory: Memory store for persistence
            notification_callback: Async function to send notifications
        """
        self.memory = memory
        self.executor = TaskExecutor(notification_callback)

    async def add_reminder(self, delay: str, message: str) -> ActionResult:
        """
        Add a one-time reminder.

        Args:
            delay: Time delay like "5m", "2h", "1d"
            message: Reminder message

        Returns:
            ActionResult with task_id if successful
        """
        try:
            # Parse delay
            delay_delta = ScheduleParser.parse_delay(delay)
            next_run = datetime.now() + delay_delta

            # Create task
            task_id = str(uuid4())[:8]
            await self.memory.create_task(
                task_id=task_id,
                task_type=TaskType.REMINDER.value,
                description=message,
                schedule_type="once",
                schedule_data={"delay": delay},
                execution_data=None,
                next_run=next_run,
            )

            logger.info(f"Created reminder {task_id}: {message} at {next_run}")
            return ActionResult(
                success=True,
                data={"task_id": task_id, "trigger_at": next_run.isoformat()},
            )
        except ValueError as e:
            return ActionResult(success=False, error=f"Invalid delay format: {e}")
        except Exception as e:
            logger.error(f"Failed to create reminder: {e}", exc_info=True)
            return ActionResult(success=False, error=str(e))

    async def add_recurring_task(
        self,
        schedule: str,
        task_type: TaskType,
        description: str,
        execution_data: dict | None = None,
    ) -> ActionResult:
        """
        Add a recurring task.

        Args:
            schedule: Schedule pattern like "daily 9am", "weekdays 6pm"
            task_type: Type of task
            description: Task description
            execution_data: Task-specific parameters

        Returns:
            ActionResult with task_id if successful
        """
        try:
            # Parse schedule
            schedule_data = ScheduleParser.parse_recurring(schedule)
            next_run = ScheduleParser.calculate_next_run(schedule_data, datetime.now())

            # Create task
            task_id = str(uuid4())[:8]
            await self.memory.create_task(
                task_id=task_id,
                task_type=task_type.value,
                description=description,
                schedule_type="recurring",
                schedule_data=schedule_data,
                execution_data=execution_data,
                next_run=next_run,
            )

            logger.info(f"Created recurring task {task_id}: {description} at {next_run}")
            return ActionResult(
                success=True,
                data={"task_id": task_id, "next_run": next_run.isoformat()},
            )
        except ValueError as e:
            return ActionResult(success=False, error=f"Invalid schedule format: {e}")
        except Exception as e:
            logger.error(f"Failed to create recurring task: {e}", exc_info=True)
            return ActionResult(success=False, error=str(e))

    async def list_tasks(self) -> list[dict]:
        """
        List all active tasks.

        Returns:
            List of task dicts with id, type, description, next_run
        """
        tasks = await self.memory.list_tasks(enabled_only=True)
        return [
            {
                "id": t["id"],
                "type": t["task_type"],
                "description": t["description"],
                "schedule_type": t["schedule_type"],
                "next_run": t["next_run"],
            }
            for t in tasks
        ]

    async def cancel_task(self, task_id: str) -> ActionResult:
        """
        Cancel a scheduled task.

        Args:
            task_id: ID of task to cancel

        Returns:
            ActionResult indicating success
        """
        task = await self.memory.get_task(task_id)
        if not task:
            return ActionResult(success=False, error=f"Task not found: {task_id}")

        await self.memory.delete_task(task_id)
        logger.info(f"Cancelled task {task_id}")
        return ActionResult(success=True, data={"task_id": task_id})

    async def check_and_execute_due_tasks(self) -> list[ActionResult]:
        """
        Check for due tasks and execute them.

        Returns:
            List of execution results
        """
        now = datetime.now()
        due_tasks = await self.memory.get_due_tasks(now)

        results = []
        for task_dict in due_tasks:
            task = ScheduledTask.from_dict(task_dict)

            # Execute task
            result = await self.executor.execute(task)
            results.append(result)

            # Update task
            if task.schedule_type == "once":
                # One-time task, disable it
                await self.memory.update_task(task.id, enabled=False, last_run=now)
                logger.info(f"Disabled one-time task {task.id}")
            else:
                # Recurring task, calculate next run
                try:
                    # Calculate from task's scheduled time, not current time
                    # This ensures proper advancement even when task is overdue
                    next_run = ScheduleParser.calculate_next_run(
                        task.schedule_data, task.next_run
                    )
                    await self.memory.update_task(
                        task.id, last_run=now, next_run=next_run
                    )
                    logger.info(f"Rescheduled task {task.id} for {next_run}")
                except Exception as e:
                    logger.error(f"Failed to reschedule task {task.id}: {e}")
                    await self.memory.update_task(task.id, enabled=False, last_run=now)

        return results
