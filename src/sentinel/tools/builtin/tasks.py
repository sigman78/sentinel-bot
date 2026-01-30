"""Task management tools."""

from sentinel.core.types import ActionResult
from sentinel.tasks.manager import TaskManager
from sentinel.tasks.types import TaskType
from sentinel.tools.base import tool
from sentinel.tools.registry import register_tool

# Global reference to task manager (set during initialization)
_task_manager: TaskManager | None = None


def set_task_manager(manager: TaskManager) -> None:
    """Set the task manager instance for tools to use."""
    global _task_manager
    _task_manager = manager


def _get_task_manager() -> TaskManager:
    """Get task manager or raise error."""
    if _task_manager is None:
        raise RuntimeError("TaskManager not initialized. Call set_task_manager() first.")
    return _task_manager


@tool(
    "add_reminder",
    "Set a one-time reminder that triggers after a delay",
    examples=[
        'add_reminder(delay="5m", message="call mom")',
        'add_reminder(delay="2h", message="check oven")',
        'add_reminder(delay="1d", message="submit report")',
    ],
)
async def add_reminder(delay: str, message: str) -> ActionResult:
    """
    Set a one-time reminder.

    Args:
        delay: Time delay like "5m", "2h", "1d"
        message: Reminder message to show when it triggers

    Returns:
        ActionResult with task_id and trigger_at if successful
    """
    manager = _get_task_manager()
    return await manager.add_reminder(delay, message)


@tool(
    "add_recurring_task",
    "Schedule a recurring task with a specific pattern",
    examples=[
        'add_recurring_task(schedule="daily 9am", description="check news")',
        'add_recurring_task(schedule="weekdays 6pm", description="workout reminder")',
        'add_recurring_task(schedule="monday 10am", description="weekly review")',
    ],
)
async def add_recurring_task(schedule: str, description: str) -> ActionResult:
    """
    Schedule a recurring reminder task.

    Args:
        schedule: Schedule pattern like "daily 9am", "weekdays 6pm", "monday 10am"
        description: Task description

    Returns:
        ActionResult with task_id and next_run if successful
    """
    manager = _get_task_manager()
    # For now, only support REMINDER type recurring tasks
    return await manager.add_recurring_task(
        schedule=schedule,
        task_type=TaskType.REMINDER,
        description=description,
    )


@tool(
    "list_tasks",
    "List all active scheduled tasks",
    examples=["list_tasks()"],
)
async def list_tasks() -> ActionResult:
    """
    List all active scheduled tasks.

    Returns:
        ActionResult with list of tasks
    """
    manager = _get_task_manager()
    tasks = await manager.list_tasks()
    return ActionResult(
        success=True,
        data={
            "tasks": tasks,
            "count": len(tasks),
        },
    )


@tool(
    "cancel_task",
    "Cancel a scheduled task by its ID",
    examples=['cancel_task(task_id="abc123")'],
)
async def cancel_task(task_id: str) -> ActionResult:
    """
    Cancel a scheduled task.

    Args:
        task_id: ID of the task to cancel

    Returns:
        ActionResult indicating success or failure
    """
    manager = _get_task_manager()
    return await manager.cancel_task(task_id)


def register_task_tools() -> None:
    """Register task management tools with the global registry."""
    register_tool(add_reminder._tool)  # type: ignore[attr-defined]
    register_tool(add_recurring_task._tool)  # type: ignore[attr-defined]
    register_tool(list_tasks._tool)  # type: ignore[attr-defined]
    register_tool(cancel_task._tool)  # type: ignore[attr-defined]
