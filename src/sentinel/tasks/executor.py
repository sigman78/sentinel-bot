"""Execute scheduled tasks."""

from collections.abc import Awaitable, Callable

from sentinel.core.logging import get_logger
from sentinel.core.types import ActionResult
from sentinel.tasks.types import ScheduledTask, TaskType

logger = get_logger("tasks.executor")


class TaskExecutor:
    """Executes different task types."""

    def __init__(self, notification_callback: Callable[[str], Awaitable[None]] | None = None):
        """
        Initialize executor.

        Args:
            notification_callback: Async function to send notifications to user
        """
        self._notification_callback = notification_callback

    async def execute(self, task: ScheduledTask) -> ActionResult:
        """
        Execute a task based on its type.

        Args:
            task: The task to execute

        Returns:
            ActionResult with success status and any data/error
        """
        logger.info(f"Executing task {task.id}: {task.description}")

        try:
            if task.task_type == TaskType.REMINDER:
                return await self._execute_reminder(task)
            elif task.task_type == TaskType.AGENT_TASK:
                return await self._execute_agent_task(task)
            elif task.task_type == TaskType.API_CALL:
                return await self._execute_api_call(task)
            elif task.task_type == TaskType.WEB_SEARCH:
                return await self._execute_web_search(task)
            else:
                return ActionResult(success=False, error=f"Unknown task type: {task.task_type}")
        except Exception as e:
            logger.error(f"Task {task.id} execution failed: {e}", exc_info=True)
            return ActionResult(success=False, error=str(e))

    async def _execute_reminder(self, task: ScheduledTask) -> ActionResult:
        """
        Execute reminder task - send notification.

        Args:
            task: Reminder task

        Returns:
            ActionResult indicating success
        """
        message = f"Reminder: {task.description}"

        if self._notification_callback:
            try:
                await self._notification_callback(message)
                logger.info(f"Reminder sent: {task.description}")
                return ActionResult(success=True, data={"message": message})
            except Exception as e:
                logger.error(f"Failed to send notification: {e}")
                return ActionResult(success=False, error=f"Notification failed: {e}")
        else:
            logger.warning("No notification callback configured")
            return ActionResult(success=False, error="No notification callback available")

    async def _execute_agent_task(self, task: ScheduledTask) -> ActionResult:
        """
        Execute agent task - delegate to agent and send result.

        TODO: Implement agent delegation.
        """
        logger.warning(f"AGENT_TASK not yet implemented: {task.id}")
        return ActionResult(success=False, error="AGENT_TASK execution not implemented yet")

    async def _execute_api_call(self, task: ScheduledTask) -> ActionResult:
        """
        Execute API call task - make HTTP request.

        TODO: Implement HTTP client.
        """
        logger.warning(f"API_CALL not yet implemented: {task.id}")
        return ActionResult(success=False, error="API_CALL execution not implemented yet")

    async def _execute_web_search(self, task: ScheduledTask) -> ActionResult:
        """
        Execute web search task - search and summarize.

        TODO: Implement web search integration.
        """
        logger.warning(f"WEB_SEARCH not yet implemented: {task.id}")
        return ActionResult(success=False, error="WEB_SEARCH execution not implemented yet")
