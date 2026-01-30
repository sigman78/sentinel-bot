"""Integration tests for tool calling with DialogAgent."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ContentType, Message
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tasks.manager import TaskManager
from sentinel.tools.builtin import register_all_builtin_tools
from sentinel.tools.builtin.tasks import set_task_manager

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


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

    return TaskManager(memory=memory, notification_callback=notify)


@pytest.fixture
def tool_registry(task_manager):
    """Create and populate tool registry."""
    # Register builtin tools
    register_all_builtin_tools()
    set_task_manager(task_manager)

    # Return global registry
    from sentinel.tools.registry import get_global_registry

    return get_global_registry()


@pytest.mark.asyncio
async def test_add_reminder_via_natural_language(memory, tool_registry):
    """Test that natural language gets converted to tool call."""
    from sentinel.core.config import get_settings
    from sentinel.llm.router import create_default_router

    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openrouter_api_key:
        pytest.skip("No API keys configured")

    llm = create_default_router()
    agent = DialogAgent(llm=llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    # User message asking to set a reminder
    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Remind me in 5 minutes to call mom",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Check that response has content
    assert response.content
    assert len(response.content) > 0

    # Check that response mentions the reminder was set
    content_lower = response.content.lower()
    assert "remind" in content_lower or "call mom" in content_lower or "set" in content_lower

    # Check that tool was actually called via native API
    assert "tool_call_count" in response.metadata
    assert response.metadata["tool_call_count"] > 0
    assert response.metadata.get("tool_results")  # Should have results


@pytest.mark.asyncio
async def test_list_tasks_via_natural_language(memory, tool_registry, task_manager):
    """Test listing tasks via natural language."""
    from sentinel.core.config import get_settings
    from sentinel.llm.router import create_default_router

    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openrouter_api_key:
        pytest.skip("No API keys configured")

    # Create a task first
    await task_manager.add_reminder("1h", "test reminder")

    llm = create_default_router()
    agent = DialogAgent(llm=llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    # Ask to list tasks
    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="What tasks do I have scheduled?",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Response should mention the task
    assert "test reminder" in response.content.lower() or "1 task" in response.content.lower()


@pytest.mark.asyncio
async def test_recurring_task_via_natural_language(memory, tool_registry):
    """Test creating recurring task via natural language."""
    from sentinel.core.config import get_settings
    from sentinel.llm.router import create_default_router

    settings = get_settings()
    if not settings.anthropic_api_key and not settings.openrouter_api_key:
        pytest.skip("No API keys configured")

    llm = create_default_router()
    agent = DialogAgent(llm=llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    # User message asking for recurring reminder
    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Remind me every weekday at 9am to check emails",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(user_msg)

    # Check response has content
    assert response.content
    assert len(response.content) > 0

    # Should mention either the schedule or confirmation
    content_lower = response.content.lower()
    assert (
        "weekday" in content_lower
        or "9am" in content_lower
        or "9:00" in content_lower
        or "email" in content_lower
        or "remind" in content_lower
    )


@pytest.mark.asyncio
async def test_tool_execution_without_llm(memory, tool_registry, task_manager):
    """Test direct tool execution without LLM (unit-style test)."""
    # This tests that tools work without requiring API keys

    # Manually create a tool call
    from sentinel.tools.executor import ToolExecutor
    from sentinel.tools.parser import ToolCall

    executor = ToolExecutor(tool_registry)

    # Test add_reminder tool
    call = ToolCall(
        tool_name="add_reminder",
        arguments={"delay": "5m", "message": "test"},
        raw_json="",
    )
    result = await executor.execute(call)
    assert result.success is True
    assert "task_id" in result.data

    # Test list_tasks tool
    call = ToolCall(tool_name="list_tasks", arguments={}, raw_json="")
    result = await executor.execute(call)
    assert result.success is True
    assert "tasks" in result.data
    assert result.data["count"] == 1  # The one we just created


@pytest.mark.asyncio
async def test_tool_call_parsing_from_llm_output():
    """Test parsing tool calls from various LLM output formats."""
    from sentinel.tools.parser import ToolParser

    # Test JSON code block
    output1 = """
I'll set that reminder for you.

```json
{
    "tool": "add_reminder",
    "args": {
        "delay": "5m",
        "message": "call mom"
    }
}
```
"""
    calls = ToolParser.extract_calls(output1)
    assert len(calls) == 1
    assert calls[0].tool_name == "add_reminder"
    assert calls[0].arguments["delay"] == "5m"

    # Test plain code block
    output2 = """
```
{"tool": "list_tasks", "args": {}}
```
"""
    calls = ToolParser.extract_calls(output2)
    assert len(calls) == 1
    assert calls[0].tool_name == "list_tasks"

    # Test inline JSON
    output3 = """
Here's what I'll do: {"tool": "get_current_time", "args": {}}
"""
    calls = ToolParser.extract_calls(output3)
    assert len(calls) == 1
    assert calls[0].tool_name == "get_current_time"
