"""Tests for graceful shutdown functionality."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from sentinel.core.types import ContentType, Message
from sentinel.interfaces.telegram import TelegramInterface


@pytest.mark.asyncio
async def test_kill_command_sets_shutdown_event(tmp_path: Path):
    """Test /kill command sets the shutdown event."""
    # Create minimal interface for testing
    interface = TelegramInterface.__new__(TelegramInterface)
    interface._shutdown_event = asyncio.Event()
    interface.owner_id = 12345

    # Mock update and context
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 12345  # Owner ID
    update.message = AsyncMock()

    context = Mock()

    # Verify shutdown event is not set
    assert not interface._shutdown_event.is_set()

    # Call handler
    await interface._handle_kill(update, context)

    # Verify shutdown event is set
    assert interface._shutdown_event.is_set()

    # Verify message was sent
    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "shutting down" in call_args.lower()


@pytest.mark.asyncio
async def test_kill_command_rejects_non_owner():
    """Test /kill command rejects non-owner users."""
    interface = TelegramInterface.__new__(TelegramInterface)
    interface._shutdown_event = asyncio.Event()
    interface.owner_id = 12345

    # Mock update with different user ID
    update = Mock()
    update.effective_user = Mock()
    update.effective_user.id = 99999  # Not the owner
    update.message = AsyncMock()

    context = Mock()

    # Call handler
    await interface._handle_kill(update, context)

    # Verify shutdown event is NOT set
    assert not interface._shutdown_event.is_set()

    # Verify no message was sent
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_stop_summarizes_conversation(tmp_path: Path):
    """Test stop() method summarizes conversation before shutting down."""
    interface = TelegramInterface.__new__(TelegramInterface)

    # Mock agent with conversation
    interface.agent = Mock()
    interface.agent.context = Mock()
    interface.agent.context.conversation = [
        Message(
            id="1",
            timestamp=datetime.now(),
            role="user",
            content="Hello",
            content_type=ContentType.TEXT,
        ),
        Message(
            id="2",
            timestamp=datetime.now(),
            role="assistant",
            content="Hi",
            content_type=ContentType.TEXT,
        ),
    ]
    interface.agent.summarize_session = AsyncMock()

    # Mock other components
    interface._orchestrator = Mock()
    interface._orchestrator.stop = AsyncMock()
    interface._router = Mock()
    interface._router.close_all = AsyncMock()
    interface.app = Mock()
    interface.app.updater = Mock()
    interface.app.updater.stop = AsyncMock()
    interface.app.stop = AsyncMock()
    interface.app.shutdown = AsyncMock()
    interface.memory = Mock()
    interface.memory.close = AsyncMock()

    # Call stop
    await interface.stop()

    # Verify summarize was called
    interface.agent.summarize_session.assert_called_once()

    # Verify all components were shut down
    interface._orchestrator.stop.assert_called_once()
    interface._router.close_all.assert_called_once()
    interface.app.updater.stop.assert_called_once()
    interface.app.stop.assert_called_once()
    interface.app.shutdown.assert_called_once()
    interface.memory.close.assert_called_once()


@pytest.mark.asyncio
async def test_stop_handles_summarize_failure():
    """Test stop() handles summarization failure gracefully."""
    interface = TelegramInterface.__new__(TelegramInterface)

    # Mock agent that fails to summarize
    interface.agent = Mock()
    interface.agent.context = Mock()
    interface.agent.context.conversation = [Mock(), Mock()]
    interface.agent.summarize_session = AsyncMock(side_effect=Exception("Summarize failed"))

    # Mock other components
    interface._orchestrator = Mock()
    interface._orchestrator.stop = AsyncMock()
    interface._router = None
    interface.app = None
    interface.memory = Mock()
    interface.memory.close = AsyncMock()

    # Should not raise exception
    await interface.stop()

    # Verify shutdown continued despite summarize failure
    interface._orchestrator.stop.assert_called_once()
    interface.memory.close.assert_called_once()
