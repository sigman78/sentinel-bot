"""Tests for awareness agent."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from sentinel.agents.awareness import AwarenessAgent


@pytest.fixture
def awareness_agent():
    """Create awareness agent with mocks."""
    llm = AsyncMock()
    memory = AsyncMock()
    return AwarenessAgent(llm=llm, memory=memory)


def test_add_reminder(awareness_agent):
    """Test adding reminders."""
    reminder_id = awareness_agent.add_reminder(
        message="Test reminder",
        trigger_at=datetime.now() + timedelta(hours=1),
    )
    assert reminder_id in awareness_agent._reminders
    assert awareness_agent._reminders[reminder_id].message == "Test reminder"


def test_remove_reminder(awareness_agent):
    """Test removing reminders."""
    reminder_id = awareness_agent.add_reminder(
        message="Test",
        trigger_at=datetime.now() + timedelta(hours=1),
    )
    assert awareness_agent.remove_reminder(reminder_id)
    assert reminder_id not in awareness_agent._reminders


def test_list_reminders(awareness_agent):
    """Test listing reminders."""
    awareness_agent.add_reminder(
        message="Test 1",
        trigger_at=datetime.now() + timedelta(hours=1),
    )
    awareness_agent.add_reminder(
        message="Test 2",
        trigger_at=datetime.now() + timedelta(hours=2),
    )
    reminders = awareness_agent.list_reminders()
    assert len(reminders) == 2


def test_add_monitor(awareness_agent):
    """Test adding monitors."""
    monitor_id = awareness_agent.add_monitor(
        name="Test monitor",
        check_fn=lambda: False,
        message="Alert message",
    )
    assert monitor_id in awareness_agent._monitors


async def test_check_expired_reminder(awareness_agent):
    """Test that expired reminders trigger notifications."""
    # Add expired reminder
    awareness_agent.add_reminder(
        message="Past due",
        trigger_at=datetime.now() - timedelta(minutes=1),
    )

    notifications = await awareness_agent.check_all()
    assert len(notifications) == 1
    assert "Past due" in notifications[0]


async def test_recurring_reminder(awareness_agent):
    """Test recurring reminders reschedule."""
    reminder_id = awareness_agent.add_reminder(
        message="Recurring",
        trigger_at=datetime.now() - timedelta(minutes=1),
        recurring=timedelta(hours=1),
    )

    await awareness_agent.check_all()

    # Should still exist (rescheduled)
    assert reminder_id in awareness_agent._reminders
    # Next run should be in the future
    assert awareness_agent._reminders[reminder_id].trigger_at > datetime.now()
