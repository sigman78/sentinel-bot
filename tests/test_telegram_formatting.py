"""Tests for Telegram markdown formatting and channel capabilities."""

from pathlib import Path

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.llm.base import LLMResponse
from sentinel.memory.store import SQLiteMemoryStore


@pytest.mark.asyncio
async def test_telegramify_basic_formatting():
    """Test that telegramify function formats markdown correctly."""
    from telegramify_markdown import telegramify
    from telegramify_markdown.type import ContentTypes

    # Test basic formatting
    boxes = await telegramify("**bold** and _italic_", max_word_count=4090)
    assert len(boxes) > 0
    assert boxes[0].content_type == ContentTypes.TEXT

    # Content should be formatted (exact format may vary)
    text = boxes[0].content
    assert "bold" in text
    assert "italic" in text


@pytest.mark.asyncio
async def test_telegramify_splits_long_messages():
    """Test that telegramify splits long messages into chunks."""
    from telegramify_markdown import telegramify
    from telegramify_markdown.type import ContentTypes

    # Create a very long message
    long_text = "This is a test. " * 1000  # Much longer than 4090 word limit

    boxes = await telegramify(long_text, max_word_count=1000)

    # Should split into multiple boxes
    assert len(boxes) >= 2
    for box in boxes:
        assert box.content_type == ContentTypes.TEXT
        # Verify content is not empty
        assert len(box.content) > 0


@pytest.mark.asyncio
async def test_dialog_agent_channel_capabilities(tmp_path: Path):
    """Test setting channel capabilities on DialogAgent."""
    from sentinel.llm.router import create_default_router

    db_path = tmp_path / "test.db"
    memory = SQLiteMemoryStore(db_path)
    await memory.connect()

    try:
        router = create_default_router()

        agent = DialogAgent(llm=router, memory=memory)
        await agent.initialize()

        # Test setting capabilities
        capabilities = "Test capabilities text"
        agent.set_channel_capabilities(capabilities)

        assert agent._channel_capabilities == capabilities
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_telegram_capabilities_in_system_prompt(tmp_path: Path):
    """Test that channel capabilities appear in system prompt."""
    from datetime import datetime
    from uuid import uuid4

    from sentinel.core.types import ContentType, Message

    # Mock LLM that captures the system prompt
    class MockLLM:
        def __init__(self):
            self.last_system_prompt = ""

        async def complete(self, messages, config, task=None, tools=None, preferred=None):
            # Capture system message
            if messages and messages[0]["role"] == "system":
                self.last_system_prompt = messages[0]["content"]

            return LLMResponse(
                content="Test response",
                model="test",
                provider="test",
                input_tokens=10,
                output_tokens=10,
                cost_usd=0.0,
            )

    db_path = tmp_path / "test.db"
    memory = SQLiteMemoryStore(db_path)
    await memory.connect()

    try:
        mock_llm = MockLLM()
        agent = DialogAgent(llm=mock_llm, memory=memory)
        await agent.initialize()

        capabilities = "## Channel Capabilities\nTelegram markdown support"
        agent.set_channel_capabilities(capabilities)

        # Process a message to trigger system prompt build
        test_msg = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content="test",
            content_type=ContentType.TEXT,
        )

        await agent.process(test_msg)

        # Verify capabilities are in system prompt
        assert "Telegram markdown" in mock_llm.last_system_prompt
        assert "Channel Capabilities" in mock_llm.last_system_prompt

    finally:
        await memory.close()
