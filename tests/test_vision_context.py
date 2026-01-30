"""Tests for context-aware image handling."""

from datetime import datetime
from uuid import uuid4

from sentinel.core.types import ContentType, Message
from sentinel.interfaces.telegram import TelegramInterface


def test_image_context_prompt_no_conversation():
    """Test image prompt when there's no conversation context."""
    interface = TelegramInterface()
    # No agent initialized, so no conversation
    prompt = interface._build_image_context_prompt()

    assert "react naturally" in prompt.lower()
    assert "meme" in prompt.lower()
    assert "screenshot" in prompt.lower()


def test_image_context_prompt_with_question():
    """Test image prompt when there's a recent question."""
    from unittest.mock import Mock

    interface = TelegramInterface()

    # Mock agent with recent conversation including a question
    mock_agent = Mock()
    mock_agent.context.conversation = [
        Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content="How do I fix this error?",
            content_type=ContentType.TEXT,
        ),
        Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="assistant",
            content="Can you show me the error?",
            content_type=ContentType.TEXT,
        ),
    ]
    interface.agent = mock_agent

    prompt = interface._build_image_context_prompt()

    assert "How do I fix this error?" in prompt
    assert "recent conversation" in prompt.lower() or "recent" in prompt.lower()
    assert "related" in prompt.lower()


def test_image_context_prompt_ongoing_discussion():
    """Test image prompt during an ongoing discussion."""
    from unittest.mock import Mock

    interface = TelegramInterface()

    # Mock agent with recent statement (no question)
    mock_agent = Mock()
    mock_agent.context.conversation = [
        Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content="I'm working on a new design for the app",
            content_type=ContentType.TEXT,
        ),
    ]
    interface.agent = mock_agent

    prompt = interface._build_image_context_prompt()

    assert "working on a new design" in prompt.lower()
    assert "discussing" in prompt.lower() or "talked about" in prompt.lower()
    assert "naturally" in prompt.lower()


def test_image_context_prompt_length():
    """Test that very long messages are truncated in prompt."""
    from unittest.mock import Mock

    interface = TelegramInterface()

    # Mock agent with very long message
    mock_agent = Mock()
    long_message = "This is a very long question " * 20  # 600+ chars
    mock_agent.context.conversation = [
        Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content=long_message,
            content_type=ContentType.TEXT,
        ),
    ]
    interface.agent = mock_agent

    prompt = interface._build_image_context_prompt()

    # Should be truncated to ~100 chars from the message
    assert len(prompt) < 500  # Reasonable total length
    assert "..." in prompt  # Truncation indicator
