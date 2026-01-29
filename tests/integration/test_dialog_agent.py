"""
Integration tests for dialog agent pipeline.

Run with: uv run pytest tests/integration -v
"""

from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ContentType, Message
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore

pytestmark = pytest.mark.integration


@pytest.fixture
async def memory_store(tmp_path: Path):
    """Temporary memory store for tests."""
    store = SQLiteMemoryStore(tmp_path / "test.db")
    await store.connect()
    yield store
    await store.close()


@pytest.fixture
def router():
    """LLM router with available providers."""
    return create_default_router()


def make_message(content: str) -> Message:
    """Create a user message."""
    return Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content=content,
        content_type=ContentType.TEXT,
    )


@pytest.mark.asyncio
async def test_dialog_agent_basic(memory_store, router):
    """Dialog agent processes message and returns response."""
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = DialogAgent(llm=llm, memory=memory_store)
    await agent.initialize()

    message = make_message("What is the capital of France? Answer in one word.")
    response = await agent.process(message)

    assert response.content
    assert "Paris" in response.content or "paris" in response.content.lower()
    assert response.role == "assistant"
    print(f"Response: {response.content}")
    print(f"Cost: ${response.metadata.get('cost_usd', 0):.4f}")

    await router.close_all()


@pytest.mark.asyncio
async def test_dialog_agent_memory_persistence(memory_store, router):
    """Dialog agent persists conversation to memory."""
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = DialogAgent(llm=llm, memory=memory_store)
    await agent.initialize()

    # First message
    msg1 = make_message("My name is TestUser.")
    await agent.process(msg1)

    # Check memory was stored
    recent = await memory_store.get_recent(limit=1)
    assert len(recent) == 1
    assert "TestUser" in recent[0].content

    await router.close_all()


@pytest.mark.asyncio
async def test_dialog_agent_conversation_context(memory_store, router):
    """Dialog agent maintains conversation context."""
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = DialogAgent(llm=llm, memory=memory_store)
    await agent.initialize()

    # Set context
    msg1 = make_message("Remember this number: 42")
    await agent.process(msg1)

    # Ask about context
    msg2 = make_message("What number did I just tell you?")
    response = await agent.process(msg2)

    assert "42" in response.content
    print(f"Context test: {response.content}")

    await router.close_all()


@pytest.mark.asyncio
async def test_dialog_agent_user_profile(memory_store, router):
    """Dialog agent loads and uses user profile."""
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    # Set user profile before agent init (uses legacy keys)
    await memory_store.set_core("user_name", "Alice")
    await memory_store.set_core("user_context", "Prefers brief responses")

    llm = router
    agent = DialogAgent(llm=llm, memory=memory_store)
    await agent.initialize()

    # Check structured profile was loaded (migrated from legacy keys)
    assert agent._user_profile.name == "Alice"
    assert "brief" in agent._user_profile.context.lower()

    await router.close_all()


@pytest.mark.asyncio
async def test_full_pipeline(memory_store, router):
    """Full pipeline: multiple turns with memory retrieval."""
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = DialogAgent(llm=llm, memory=memory_store)
    await agent.initialize()

    # Turn 1: Introduce topic
    r1 = await agent.process(make_message("I'm working on a Python project called Sentinel."))
    print(f"Turn 1: {r1.content[:100]}...")

    # Turn 2: Ask follow-up
    r2 = await agent.process(make_message("What project am I working on?"))
    assert "Sentinel" in r2.content or "sentinel" in r2.content.lower()
    print(f"Turn 2: {r2.content[:100]}...")

    # Verify conversation length
    assert len(agent.context.conversation) == 4  # 2 user + 2 assistant

    # Verify memories stored
    recent = await memory_store.get_recent(limit=5)
    assert len(recent) >= 2

    await router.close_all()
