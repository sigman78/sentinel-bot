"""Tests for orchestrator and background agents."""

from datetime import datetime, timedelta

import pytest

from sentinel.core.orchestrator import Orchestrator, ScheduledTask, TaskPriority


@pytest.fixture
def orchestrator():
    return Orchestrator()


def test_schedule_task(orchestrator):
    """Test task scheduling."""
    called = []

    def callback():
        called.append(datetime.now())

    orchestrator.schedule_task(
        task_id="test",
        name="Test task",
        callback=callback,
        interval=timedelta(seconds=1),
    )

    assert "test" in orchestrator._tasks
    assert orchestrator._tasks["test"].name == "Test task"


def test_cancel_task(orchestrator):
    """Test task cancellation."""
    orchestrator.schedule_task(
        task_id="test",
        name="Test task",
        callback=lambda: None,
    )
    assert orchestrator.cancel_task("test")
    assert "test" not in orchestrator._tasks


def test_mark_activity(orchestrator):
    """Test activity marking."""
    old_activity = orchestrator._last_activity
    orchestrator.mark_activity()
    assert orchestrator._last_activity >= old_activity


def test_idle_detection(orchestrator):
    """Test idle detection."""
    # After marking activity, should not be idle
    orchestrator.mark_activity()
    assert not orchestrator.is_idle()

    # Simulate old activity
    orchestrator._last_activity = datetime.now() - timedelta(minutes=10)
    assert orchestrator.is_idle()


def test_task_priority():
    """Test task priority ordering."""
    tasks = [
        ScheduledTask(
            id="low",
            name="Low",
            callback=lambda: None,
            priority=TaskPriority.LOW,
        ),
        ScheduledTask(
            id="high",
            name="High",
            callback=lambda: None,
            priority=TaskPriority.HIGH,
        ),
        ScheduledTask(
            id="normal",
            name="Normal",
            callback=lambda: None,
            priority=TaskPriority.NORMAL,
        ),
    ]
    sorted_tasks = sorted(tasks, key=lambda t: t.priority.value, reverse=True)
    assert sorted_tasks[0].id == "high"
    assert sorted_tasks[1].id == "normal"
    assert sorted_tasks[2].id == "low"


async def test_orchestrator_start_stop():
    """Test orchestrator lifecycle."""
    orch = Orchestrator()
    await orch.start()
    assert orch._running
    await orch.stop()
    assert not orch._running
