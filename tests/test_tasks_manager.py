"""Tests for task manager."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.manager import TaskManager
from sentinel.tasks.types import TaskType


@pytest.fixture
async def memory():
    """Create temporary memory store."""
    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        store = SQLiteMemoryStore(db_path)
        await store.connect()
        yield store
        await store.close()


@pytest.fixture
def notification_log():
    """Track notifications sent."""
    return []


@pytest.fixture
async def task_manager(memory, notification_log):
    """Create task manager with notification tracking."""

    async def notify(message: str):
        notification_log.append(message)

    return TaskManager(memory=memory, notification_callback=notify)


@pytest.mark.asyncio
async def test_add_reminder(task_manager):
    """Test adding a one-time reminder."""
    result = await task_manager.add_reminder("5m", "test reminder")

    assert result.success is True
    assert "task_id" in result.data
    assert "trigger_at" in result.data

    # Verify task is in database
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["description"] == "test reminder"
    assert tasks[0]["type"] == "reminder"
    assert tasks[0]["schedule_type"] == "once"


@pytest.mark.asyncio
async def test_add_recurring_task(task_manager):
    """Test adding a recurring task."""
    result = await task_manager.add_recurring_task(
        schedule="daily 9am",
        task_type=TaskType.REMINDER,
        description="daily reminder",
    )

    assert result.success is True
    assert "task_id" in result.data
    assert "next_run" in result.data

    # Verify task is in database
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["description"] == "daily reminder"
    assert tasks[0]["schedule_type"] == "recurring"


@pytest.mark.asyncio
async def test_execute_due_reminder(task_manager, memory, notification_log):
    """Test executing a due reminder."""
    # Create reminder that's already due
    past_time = datetime.now() - timedelta(minutes=1)
    await memory.create_task(
        task_id="test123",
        task_type="reminder",
        description="test message",
        schedule_type="once",
        schedule_data={"delay": "1m"},
        execution_data=None,
        next_run=past_time,
    )

    # Execute due tasks
    results = await task_manager.check_and_execute_due_tasks()

    # Should have executed 1 task
    assert len(results) == 1
    assert results[0].success is True

    # Should have sent notification
    assert len(notification_log) == 1
    assert "test message" in notification_log[0]

    # Task should be disabled (one-time)
    tasks = await memory.list_tasks(enabled_only=True)
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_recurring_task_reschedule(task_manager, memory):
    """Test recurring task gets rescheduled after execution."""
    # Create recurring task that's due
    past_time = datetime.now() - timedelta(minutes=1)
    await memory.create_task(
        task_id="recurring123",
        task_type="reminder",
        description="daily task",
        schedule_type="recurring",
        schedule_data={"pattern": "daily", "time": "09:00"},
        execution_data=None,
        next_run=past_time,
    )

    # Execute due tasks
    await task_manager.check_and_execute_due_tasks()

    # Task should still be enabled
    tasks = await memory.list_tasks(enabled_only=True)
    assert len(tasks) == 1

    # Next run should be in the future
    task = await memory.get_task("recurring123")
    # next_run is already a datetime object from SQLite
    next_run = (
        task["next_run"]
        if isinstance(task["next_run"], datetime)
        else datetime.fromisoformat(task["next_run"])
    )
    assert next_run > datetime.now()


@pytest.mark.asyncio
async def test_cancel_task(task_manager):
    """Test cancelling a task."""
    # Create task
    result = await task_manager.add_reminder("5m", "test")
    task_id = result.data["task_id"]

    # Cancel it
    cancel_result = await task_manager.cancel_task(task_id)
    assert cancel_result.success is True

    # Should be gone
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 0


@pytest.mark.asyncio
async def test_invalid_delay(task_manager):
    """Test invalid delay format."""
    result = await task_manager.add_reminder("invalid", "test")
    assert result.success is False
    assert "Invalid delay format" in result.error


@pytest.mark.asyncio
async def test_invalid_schedule(task_manager):
    """Test invalid schedule pattern."""
    result = await task_manager.add_recurring_task(
        schedule="invalid pattern",
        task_type=TaskType.REMINDER,
        description="test",
    )
    assert result.success is False
    assert "Invalid schedule format" in result.error
