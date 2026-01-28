"""Tests for dynamic importance scoring in DialogAgent."""

from datetime import datetime

from sentinel.agents.dialog import DialogAgent
from sentinel.core.types import ContentType, Message


def test_calculate_exchange_importance_base():
    """Test base importance score for simple exchange."""
    # Create a minimal DialogAgent instance (no LLM needed for this test)
    agent = DialogAgent.__new__(DialogAgent)

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Hello",
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content="Hi there!",
        content_type=ContentType.TEXT,
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Base score is 0.3, short messages get no bonus
    assert 0.3 <= importance <= 0.4, f"Expected ~0.3, got {importance}"


def test_calculate_exchange_importance_long_message():
    """Test importance increases with message length."""
    agent = DialogAgent.__new__(DialogAgent)

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="This is a much longer message " * 20,  # ~600 chars
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content="Here is a detailed response " * 10,  # ~280 chars
        content_type=ContentType.TEXT,
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Base (0.3) + length bonus (0.2) = ~0.5+
    assert importance >= 0.5, f"Long messages should score higher, got {importance}"


def test_calculate_exchange_importance_with_tools():
    """Test importance increases when tools are used."""
    agent = DialogAgent.__new__(DialogAgent)

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Set a reminder for 5pm",
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content="I've set the reminder.",
        content_type=ContentType.TEXT,
        metadata={"tool_calls": [{"name": "add_reminder", "args": {}}]},
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Base (0.3) + tool bonus (0.1) = ~0.4+
    assert importance >= 0.4, f"Tool usage should increase importance, got {importance}"


def test_calculate_exchange_importance_with_keywords():
    """Test importance increases with important keywords."""
    agent = DialogAgent.__new__(DialogAgent)

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content="Remember to always use type hints when coding. This is important.",
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content="I'll remember that preference.",
        content_type=ContentType.TEXT,
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Base (0.3) + keywords (remember, always, important = 0.15) = ~0.45+
    assert importance >= 0.45, f"Keywords should increase importance, got {importance}"


def test_calculate_exchange_importance_complex():
    """Test importance for complex exchange with multiple factors."""
    agent = DialogAgent.__new__(DialogAgent)

    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content=(
            "This is an important decision about the project architecture. "
            "I need help choosing between PostgreSQL and MongoDB. "
            "Remember that we prefer type-safe solutions."
        ),
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content=(
            "Let me analyze both options for you. " * 20  # Long response
        ),
        content_type=ContentType.TEXT,
        metadata={
            "tool_calls": [{"name": "search_docs", "args": {}}],
            "cost_usd": 0.015,  # Expensive response
        },
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Base (0.3) + length (0.2) + tool (0.1) + keywords (0.15+) + cost (0.2) = ~0.95+
    assert importance >= 0.8, f"Complex exchange should score high, got {importance}"


def test_calculate_exchange_importance_capped_at_one():
    """Test importance is capped at 1.0."""
    agent = DialogAgent.__new__(DialogAgent)

    # Create an exchange with all possible bonuses
    user_msg = Message(
        id="1",
        timestamp=datetime.now(),
        role="user",
        content=(
            "Important urgent decision: Remember to always help me with errors. " * 10
        ),
        content_type=ContentType.TEXT,
    )
    assistant_msg = Message(
        id="2",
        timestamp=datetime.now(),
        role="assistant",
        content="Detailed response " * 100,
        content_type=ContentType.TEXT,
        metadata={
            "tool_calls": [{"name": "tool1"}, {"name": "tool2"}, {"name": "tool3"}],
            "cost_usd": 0.05,
        },
    )

    importance = agent._calculate_exchange_importance(user_msg, assistant_msg)

    # Should be capped at 1.0
    assert importance <= 1.0, f"Importance should be capped at 1.0, got {importance}"
    assert importance >= 0.9, f"High-value exchange should score near 1.0, got {importance}"
