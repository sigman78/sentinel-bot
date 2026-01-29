"""Integration tests for agenda tools with real DialogAgent."""


import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.tools.builtin import register_all_builtin_tools
from sentinel.tools.builtin.agenda import set_data_dir
from sentinel.tools.registry import get_global_registry


@pytest.fixture
async def setup_agent(tmp_path):
    """Set up DialogAgent with agenda tools."""
    # Create data directory with agenda file
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    agenda_path = data_dir / "agenda.md"
    agenda_content = """# Project agenda
This document used to track long and short term plans, priorities, context

## Current tasks and goals
(Filled by agent on a go)

## Active plans
(Filled by agent on a go)

## Future plans
(Filled by agent on a go)

## Preferences and experience
(Filled by agent on a go)

## Work notes
(Filled by agent on a go)
"""
    agenda_path.write_text(agenda_content, encoding="utf-8")

    # Initialize tools
    register_all_builtin_tools()
    set_data_dir(data_dir)

    # Create agent
    db_path = tmp_path / "test.db"
    memory = SQLiteMemoryStore(db_path)
    await memory.connect()

    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    tool_registry = get_global_registry()

    agent = DialogAgent(llm=llm, memory=memory, tool_registry=tool_registry)
    await agent.initialize()

    yield agent, agenda_path

    await memory.close()


@pytest.mark.asyncio
async def test_check_agenda_tool_exists(setup_agent):
    """Verify check_agenda tool is registered."""
    agent, _ = setup_agent
    registry = agent._tool_registry

    tools = registry.get_all()
    tool_names = [t.name for t in tools]

    assert "check_agenda" in tool_names
    assert "update_agenda" in tool_names


@pytest.mark.asyncio
async def test_agenda_tools_format(setup_agent):
    """Verify agenda tools have correct OpenAI/Anthropic format."""
    agent, _ = setup_agent
    registry = agent._tool_registry

    # Test OpenAI format
    openai_tools = registry.to_openai_tools()
    tool_names = [t["function"]["name"] for t in openai_tools]
    assert "check_agenda" in tool_names
    assert "update_agenda" in tool_names

    # Test Anthropic format
    anthropic_tools = registry.to_anthropic_tools()
    tool_names = [t["name"] for t in anthropic_tools]
    assert "check_agenda" in tool_names
    assert "update_agenda" in tool_names

    # Verify update_agenda has parameters
    update_tool = next(t for t in anthropic_tools if t["name"] == "update_agenda")
    assert "input_schema" in update_tool
    assert "section" in update_tool["input_schema"]["properties"]
    assert "content" in update_tool["input_schema"]["properties"]
