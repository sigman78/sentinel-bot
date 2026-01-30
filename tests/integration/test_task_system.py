"""Integration tests for task system."""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sentinel.core.logging import get_logger
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.manager import TaskManager
from sentinel.tasks.types import TaskType

logger = get_logger("tests.integration.task_system")


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
    """Track notifications."""
    return []


@pytest.fixture
async def task_manager(memory, notification_log):
    """Create task manager."""

    async def notify(message: str):
        notification_log.append(message)
        logger.info(f"NOTIFICATION: {message}")

    return TaskManager(memory=memory, notification_callback=notify)


@pytest.mark.asyncio
async def test_end_to_end_reminder_flow(task_manager, notification_log):
    """Test complete reminder flow: create → wait → execute → notify."""
    # Create reminder that triggers in 2 seconds
    result = await task_manager.add_reminder("2s", "test reminder")
    assert result.success is True
    task_id = result.data["task_id"]

    logger.info(f"Created reminder {task_id}")

    # Check it's in the list
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id

    # Wait for it to become due
    await asyncio.sleep(2.5)

    # Execute due tasks
    results = await task_manager.check_and_execute_due_tasks()
    assert len(results) == 1
    assert results[0].success is True

    # Check notification was sent
    assert len(notification_log) == 1
    assert "test reminder" in notification_log[0]

    # Check task is no longer active (one-time)
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 0

    logger.info("End-to-end reminder test passed")


@pytest.mark.asyncio
async def test_recurring_task_multiple_executions(task_manager, memory, notification_log):
    """Test recurring task executes multiple times and properly advances schedule."""
    # Create task scheduled for yesterday at 9am (past due)
    yesterday_9am = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=1)

    await memory.create_task(
        task_id="recurring_test",
        task_type="reminder",
        description="recurring reminder",
        schedule_type="recurring",
        schedule_data={"pattern": "daily", "time": "09:00"},
        execution_data=None,
        next_run=yesterday_9am,
    )

    # First execution
    results = await task_manager.check_and_execute_due_tasks()
    assert len(results) == 1
    assert len(notification_log) == 1

    # Check it was rescheduled to today at 9am
    task = await memory.get_task("recurring_test")
    assert task is not None
    assert task["enabled"] is True
    first_next_run = task["next_run"]  # Already a datetime object
    # Should be today at 9am
    expected = yesterday_9am + timedelta(days=1)
    assert first_next_run == expected

    # Manually set to yesterday again (simulate another day passing)
    await memory.update_task(
        "recurring_test", next_run=yesterday_9am - timedelta(days=1)  # 2 days ago
    )

    # Second execution
    results = await task_manager.check_and_execute_due_tasks()
    assert len(results) == 1
    assert len(notification_log) == 2

    # Still active and rescheduled
    task = await memory.get_task("recurring_test")
    assert task["enabled"] is True
    second_next_run = task["next_run"]  # Already a datetime object
    # Should advance from 2 days ago to 1 day ago
    assert second_next_run == (yesterday_9am - timedelta(days=1)) + timedelta(days=1)

    logger.info("Recurring task multiple executions test passed")


@pytest.mark.asyncio
async def test_multiple_tasks_priority(task_manager, memory, notification_log):
    """Test multiple tasks due at same time all execute."""
    now = datetime.now()
    past_time = now - timedelta(minutes=1)

    # Create 3 tasks all due
    for i in range(3):
        await memory.create_task(
            task_id=f"task_{i}",
            task_type="reminder",
            description=f"reminder {i}",
            schedule_type="once",
            schedule_data={"delay": "1m"},
            execution_data=None,
            next_run=past_time,
        )

    # Execute all
    results = await task_manager.check_and_execute_due_tasks()

    # All 3 should execute
    assert len(results) == 3
    assert all(r.success for r in results)
    assert len(notification_log) == 3

    # All should be disabled
    tasks = await task_manager.list_tasks()
    assert len(tasks) == 0

    logger.info("Multiple tasks priority test passed")


@pytest.mark.asyncio
async def test_task_persistence_across_restart(memory, notification_log):
    """Test tasks persist and work after 'restart' (new manager instance)."""
    # First manager - create task
    async def notify1(msg):
        notification_log.append(("manager1", msg))

    manager1 = TaskManager(memory=memory, notification_callback=notify1)
    result = await manager1.add_reminder("1h", "persistent reminder")
    assert result.success is True
    task_id = result.data["task_id"]

    # Simulate restart - new manager instance with same database
    async def notify2(msg):
        notification_log.append(("manager2", msg))

    manager2 = TaskManager(memory=memory, notification_callback=notify2)

    # Task should still be there
    tasks = await manager2.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == task_id

    # Manually make it due
    await memory.update_task(task_id, next_run=datetime.now() - timedelta(seconds=1))

    # New manager can execute it
    results = await manager2.check_and_execute_due_tasks()
    assert len(results) == 1
    assert results[0].success is True

    # Notification sent via second manager's callback
    assert len(notification_log) == 1
    assert notification_log[0][0] == "manager2"

    logger.info("Task persistence test passed")


@pytest.mark.asyncio
async def test_notification_failure_handling(memory):
    """Test task execution handles notification failures gracefully."""
    failure_count = 0

    async def failing_notify(msg):
        nonlocal failure_count
        failure_count += 1
        raise RuntimeError("Notification service down")

    manager = TaskManager(memory=memory, notification_callback=failing_notify)

    # Create task that's due
    past_time = datetime.now() - timedelta(seconds=1)
    await memory.create_task(
        task_id="notify_fail_test",
        task_type="reminder",
        description="test",
        schedule_type="once",
        schedule_data={"delay": "1s"},
        execution_data=None,
        next_run=past_time,
    )

    # Execute - should not crash despite notification failure
    results = await manager.check_and_execute_due_tasks()
    assert len(results) == 1
    # Task execution itself failed because notification failed
    assert results[0].success is False
    assert "Notification failed" in results[0].error

    # But task should still be disabled (one-time)
    task = await memory.get_task("notify_fail_test")
    assert task["enabled"] is False

    logger.info("Notification failure handling test passed")


@pytest.mark.asyncio
async def test_weekday_recurring_calculation(task_manager, memory):
    """Test weekday pattern correctly skips weekends."""
    # Create weekday task
    result = await task_manager.add_recurring_task(
        schedule="weekdays 9am",
        task_type=TaskType.REMINDER,
        description="weekday test",
    )
    assert result.success is True

    task_id = result.data["task_id"]
    task = await memory.get_task(task_id)
    next_run = task["next_run"]

    # Should never be Saturday (5) or Sunday (6)
    assert next_run.weekday() < 5

    # Manually set to a past Friday evening and reschedule
    friday_evening = datetime.now() - timedelta(days=7)  # Go back a week
    while friday_evening.weekday() != 4:  # Find Friday
        friday_evening += timedelta(days=1)
    friday_evening = friday_evening.replace(hour=20, minute=0, second=0, microsecond=0)

    await memory.update_task(task_id, next_run=friday_evening)

    # Execute (will reschedule)
    results = await task_manager.check_and_execute_due_tasks()

    # Next run should be Monday, not Saturday
    task = await memory.get_task(task_id)
    next_run = task["next_run"]
    assert next_run.weekday() == 0  # Monday

    logger.info("Weekday recurring calculation test passed")


@pytest.mark.asyncio
async def test_task_list_ordering(task_manager):
    """Test tasks are listed in next_run order."""
    now = datetime.now()

    # Create tasks with different next_run times
    await task_manager.add_reminder("5m", "task 1")
    await task_manager.add_reminder("1m", "task 2")
    await task_manager.add_reminder("10m", "task 3")

    tasks = await task_manager.list_tasks()
    assert len(tasks) == 3

    # Should be ordered by next_run (earliest first)
    next_runs = [t["next_run"] for t in tasks]
    assert next_runs == sorted(next_runs)

    logger.info("Task list ordering test passed")


@pytest.mark.asyncio
async def test_database_schema_migration(memory):
    """Test scheduled_tasks table exists and has correct schema."""
    # Verify table exists
    async with memory.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduled_tasks'"
    ) as cursor:
        result = await cursor.fetchone()
        assert result is not None

    # Verify index exists
    async with memory.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_tasks_next_run'"
    ) as cursor:
        result = await cursor.fetchone()
        assert result is not None

    # Verify columns
    async with memory.conn.execute("PRAGMA table_info(scheduled_tasks)") as cursor:
        columns = {row[1] for row in await cursor.fetchall()}
        expected_columns = {
            "id",
            "task_type",
            "description",
            "schedule_type",
            "schedule_data",
            "execution_data",
            "enabled",
            "created_at",
            "last_run",
            "next_run",
        }
        assert columns == expected_columns

    logger.info("Database schema migration test passed")


@pytest.mark.asyncio
async def test_cancel_nonexistent_task(task_manager):
    """Test canceling non-existent task returns error."""
    result = await task_manager.cancel_task("nonexistent_id")
    assert result.success is False
    assert "not found" in result.error.lower()


@pytest.mark.asyncio
async def test_empty_task_list(task_manager):
    """Test listing tasks when none exist."""
    tasks = await task_manager.list_tasks()
    assert tasks == []


@pytest.mark.asyncio
async def test_specific_day_pattern_advance(task_manager, memory):
    """Test specific day pattern advances correctly across weeks."""
    # Find last Monday at 10am
    last_monday = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
    while last_monday.weekday() != 0:
        last_monday -= timedelta(days=1)
    # If today is Monday after 10am, go back a week
    if last_monday >= datetime.now():
        last_monday -= timedelta(days=7)

    # Create task scheduled for last Monday (past due)
    await memory.create_task(
        task_id="monday_test",
        task_type="reminder",
        description="monday test",
        schedule_type="recurring",
        schedule_data={"pattern": "monday", "time": "10:00"},
        execution_data=None,
        next_run=last_monday,
    )

    # Execute - should reschedule to next Monday
    await task_manager.check_and_execute_due_tasks()

    # Check rescheduled correctly
    task = await memory.get_task("monday_test")
    first_next_run = task["next_run"]
    assert first_next_run.weekday() == 0  # Still Monday
    # Should be 7 days after last Monday
    assert (first_next_run - last_monday).days == 7

    # Set to 2 weeks ago and execute again
    two_weeks_ago = last_monday - timedelta(days=7)
    await memory.update_task("monday_test", next_run=two_weeks_ago)
    await task_manager.check_and_execute_due_tasks()

    # Should advance to 1 week ago
    task = await memory.get_task("monday_test")
    second_next_run = task["next_run"]
    assert second_next_run.weekday() == 0
    assert (second_next_run - two_weeks_ago).days == 7

    logger.info("Specific day pattern advance test passed")
