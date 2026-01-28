"""Test DialogAgent with tool calling."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ActionResult, ContentType, Message
from sentinel.llm.base import LLMResponse, ProviderType
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tools.base import tool
from sentinel.tools.registry import ToolRegistry


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
def mock_llm():
    """Create mock LLM provider."""
    llm = Mock()
    llm.complete = AsyncMock()
    llm.provider_type = Mock()
    llm.provider_type.value = "claude"
    return llm


@pytest.fixture
def tool_registry():
    """Create tool registry with test tool."""
    registry = ToolRegistry()

    @tool("test_tool", "A test tool")
    async def test_tool(arg: str) -> ActionResult:
        """Test tool that returns its argument."""
        return ActionResult(success=True, data={"result": f"processed {arg}"})

    registry.register(test_tool._tool)
    return registry


@pytest.mark.asyncio
async def test_dialog_with_tool_call(memory, mock_llm, tool_registry):
    """Test DialogAgent processes tool calls correctly."""

    # First LLM call returns native tool call
    first_response = LLMResponse(
        content="",
        model="test-model",
        provider=ProviderType.CLAUDE,
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
        tool_calls=[
            {
                "id": "call_123",
                "name": "test_tool",
                "input": {"arg": "hello"},
            }
        ],
    )

    # Second LLM call returns natural language
    second_response = LLMResponse(
        content="I processed 'hello' for you.",
        model="test-model",
        provider=ProviderType.CLAUDE,
        input_tokens=15,
        output_tokens=10,
        cost_usd=0.0005,
    )

    # Configure mock to return different responses
    mock_llm.complete.side_effect = [first_response, second_response]

    # Create agent with tools
    agent = DialogAgent(llm=mock_llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    # Process user message
    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Process hello",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Check response
    assert response.content == "I processed 'hello' for you."
    assert response.metadata.get("tool_calls") == 1
    assert response.metadata.get("tool_results") == [True]

    # Check LLM was called twice
    assert mock_llm.complete.call_count == 2


@pytest.mark.asyncio
async def test_dialog_with_empty_final_response(memory, mock_llm, tool_registry):
    """Test DialogAgent handles empty final response gracefully."""

    # First LLM call returns native tool call
    first_response = LLMResponse(
        content="",
        model="test-model",
        provider=ProviderType.CLAUDE,
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
        tool_calls=[
            {
                "id": "call_456",
                "name": "test_tool",
                "input": {"arg": "test"},
            }
        ],
    )

    # Second LLM call returns empty string (bug scenario)
    second_response = LLMResponse(
        content="",
        model="test-model",
        provider=ProviderType.CLAUDE,
        input_tokens=15,
        output_tokens=0,
        cost_usd=0.0005,
    )

    mock_llm.complete.side_effect = [first_response, second_response]

    agent = DialogAgent(llm=mock_llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Test",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Should fall back to formatted tool results
    assert response.content  # Not empty
    assert "processed test" in response.content or "Tool" in response.content


@pytest.mark.asyncio
async def test_dialog_without_tool_calls(memory, mock_llm, tool_registry):
    """Test DialogAgent works normally without tool calls."""

    # LLM returns regular response (no tools)
    llm_response = LLMResponse(
        content="This is a regular response without tools.",
        model="test-model",
        provider=ProviderType.CLAUDE,
        input_tokens=10,
        output_tokens=20,
        cost_usd=0.001,
    )

    mock_llm.complete.return_value = llm_response

    agent = DialogAgent(llm=mock_llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Hello",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Check response
    assert response.content == "This is a regular response without tools."
    assert "tool_calls" not in response.metadata

    # Check LLM was called only once
    assert mock_llm.complete.call_count == 1
