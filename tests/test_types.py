"""Tests for core types."""

from datetime import datetime

from sentinel.core.types import ContentType, Message


def test_message_to_llm_format():
    """Message converts to LLM API format."""
    msg = Message(
        id="test-1",
        timestamp=datetime.now(),
        role="user",
        content="Hello",
    )
    result = msg.to_llm_format()
    assert result == {"role": "user", "content": "Hello"}


def test_message_default_content_type():
    """Message defaults to TEXT content type."""
    msg = Message(
        id="test-2",
        timestamp=datetime.now(),
        role="assistant",
        content="Hi there",
    )
    assert msg.content_type == ContentType.TEXT
