"""Tests for memory store."""

from datetime import datetime
from pathlib import Path

import pytest

from sentinel.memory.base import MemoryEntry, MemoryType
from sentinel.memory.profile import UserProfile
from sentinel.memory.store import SQLiteMemoryStore


@pytest.fixture
async def memory_store(tmp_path: Path):
    """Create a temporary memory store."""
    store = SQLiteMemoryStore(tmp_path / "test.db")
    await store.connect()
    yield store
    await store.close()


@pytest.mark.asyncio
async def test_core_memory(memory_store: SQLiteMemoryStore):
    """Core memory get/set works."""
    await memory_store.set_core("user_name", "Alice")
    result = await memory_store.get_core("user_name")
    assert result == "Alice"


@pytest.mark.asyncio
async def test_core_memory_update(memory_store: SQLiteMemoryStore):
    """Core memory can be updated."""
    await memory_store.set_core("key", "value1")
    await memory_store.set_core("key", "value2")
    result = await memory_store.get_core("key")
    assert result == "value2"


@pytest.mark.asyncio
async def test_store_episodic(memory_store: SQLiteMemoryStore):
    """Episodic memory storage works."""
    entry = MemoryEntry(
        id="ep-1",
        type=MemoryType.EPISODIC,
        content="User asked about weather",
        timestamp=datetime.now(),
        importance=0.7,
    )
    entry_id = await memory_store.store(entry)
    assert entry_id == "ep-1"

    retrieved = await memory_store.get("ep-1")
    assert retrieved is not None
    assert retrieved.content == "User asked about weather"


@pytest.mark.asyncio
async def test_store_semantic(memory_store: SQLiteMemoryStore):
    """Semantic memory storage works."""
    entry = MemoryEntry(
        id="fact-1",
        type=MemoryType.SEMANTIC,
        content="User prefers dark mode",
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)

    retrieved = await memory_store.get("fact-1")
    assert retrieved is not None
    assert retrieved.type == MemoryType.SEMANTIC


@pytest.mark.asyncio
async def test_delete_memory(memory_store: SQLiteMemoryStore):
    """Memory deletion works."""
    entry = MemoryEntry(
        id="del-1",
        type=MemoryType.EPISODIC,
        content="Temporary",
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)
    await memory_store.delete("del-1")

    result = await memory_store.get("del-1")
    assert result is None


@pytest.mark.asyncio
async def test_get_recent(memory_store: SQLiteMemoryStore):
    """Recent memories retrieval works."""
    for i in range(3):
        entry = MemoryEntry(
            id=f"recent-{i}",
            type=MemoryType.EPISODIC,
            content=f"Event {i}",
            timestamp=datetime.now(),
        )
        await memory_store.store(entry)

    recent = await memory_store.get_recent(limit=2)
    assert len(recent) == 2


@pytest.mark.asyncio
async def test_user_profile_core_memory(memory_store: SQLiteMemoryStore):
    """User profile stored in core memory."""
    await memory_store.set_core("user_name", "TestUser")
    await memory_store.set_core("user_context", "Prefers concise responses")

    name = await memory_store.get_core("user_name")
    context = await memory_store.get_core("user_context")

    assert name == "TestUser"
    assert context == "Prefers concise responses"


@pytest.mark.asyncio
async def test_fts_search_basic(memory_store: SQLiteMemoryStore):
    """FTS search finds relevant memories."""
    entry = MemoryEntry(
        id="search-1",
        type=MemoryType.EPISODIC,
        content="User asked about Python programming",
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)

    results = await memory_store.retrieve("Python")
    assert len(results) == 1
    assert results[0].id == "search-1"


@pytest.mark.asyncio
async def test_fts_search_with_comma(memory_store: SQLiteMemoryStore):
    """FTS search handles queries with commas."""
    entry = MemoryEntry(
        id="comma-1",
        type=MemoryType.EPISODIC,
        content="User likes apples, oranges, and bananas",
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)

    # Search with comma should not cause syntax error
    results = await memory_store.retrieve("apples, oranges")
    assert len(results) == 1
    assert results[0].id == "comma-1"


@pytest.mark.asyncio
async def test_fts_search_with_quotes(memory_store: SQLiteMemoryStore):
    """FTS search handles queries with quotes."""
    entry = MemoryEntry(
        id="quote-1",
        type=MemoryType.SEMANTIC,
        content='User said "hello world" in chat',
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)

    # Search with quotes should not cause syntax error
    results = await memory_store.retrieve('"hello world"')
    assert len(results) == 1
    assert results[0].id == "quote-1"


@pytest.mark.asyncio
async def test_fts_search_with_special_chars(memory_store: SQLiteMemoryStore):
    """FTS search handles queries with FTS5 operators."""
    entry = MemoryEntry(
        id="special-1",
        type=MemoryType.EPISODIC,
        content="User asked about C++ AND Python OR Java",
        timestamp=datetime.now(),
    )
    await memory_store.store(entry)

    # Search with FTS5 keywords should be treated as literals
    results = await memory_store.retrieve("C++ AND Python")
    assert len(results) == 1
    assert results[0].id == "special-1"


@pytest.mark.asyncio
async def test_fts_escape_query(memory_store: SQLiteMemoryStore):
    """Test FTS query escaping method."""
    # Test basic escaping
    assert memory_store._escape_fts_query("hello") == '"hello"'

    # Test quote escaping
    assert memory_store._escape_fts_query('say "hi"') == '"say ""hi"""'

    # Test comma handling
    assert memory_store._escape_fts_query("a, b, c") == '"a, b, c"'


@pytest.mark.asyncio
async def test_retrieval_importance_ranking(memory_store: SQLiteMemoryStore):
    """Test that retrieval ranks by importance, not just FTS score."""
    from datetime import timedelta

    # Create memories with different importance scores, same content
    now = datetime.now()

    low_importance = MemoryEntry(
        id="low-imp",
        type=MemoryType.EPISODIC,
        content="Python programming discussion about functions",
        timestamp=now - timedelta(days=1),
        importance=0.3,  # Low importance
    )
    high_importance = MemoryEntry(
        id="high-imp",
        type=MemoryType.EPISODIC,
        content="Python programming discussion about classes",
        timestamp=now - timedelta(days=1),
        importance=0.9,  # High importance
    )

    await memory_store.store(low_importance)
    await memory_store.store(high_importance)

    # Search for "Python programming"
    results = await memory_store.retrieve("Python programming")

    # High importance should rank first
    assert len(results) >= 2
    assert results[0].id == "high-imp", "High importance memory should rank first"


@pytest.mark.asyncio
async def test_retrieval_recency_ranking(memory_store: SQLiteMemoryStore):
    """Test that retrieval considers recency in ranking."""
    from datetime import timedelta

    now = datetime.now()

    # Create memories with same importance, different ages
    old_memory = MemoryEntry(
        id="old-mem",
        type=MemoryType.EPISODIC,
        content="Discussion about async programming patterns",
        timestamp=now - timedelta(days=60),  # Old
        importance=0.5,
    )
    recent_memory = MemoryEntry(
        id="recent-mem",
        type=MemoryType.EPISODIC,
        content="Discussion about async programming best practices",
        timestamp=now - timedelta(hours=2),  # Recent
        importance=0.5,
    )

    await memory_store.store(old_memory)
    await memory_store.store(recent_memory)

    # Search for "async programming"
    results = await memory_store.retrieve("async programming")

    # Recent memory should rank higher (all else being equal)
    assert len(results) >= 2
    assert results[0].id == "recent-mem", "Recent memory should rank first"


@pytest.mark.asyncio
async def test_retrieval_composite_ranking(memory_store: SQLiteMemoryStore):
    """Test that retrieval balances relevance, importance, and recency."""
    from datetime import timedelta

    now = datetime.now()

    # Scenario: Old but very important vs recent but less important
    old_important = MemoryEntry(
        id="old-important",
        type=MemoryType.EPISODIC,
        content="Critical system architecture decision about database schema",
        timestamp=now - timedelta(days=30),
        importance=0.95,  # Very important
    )
    recent_less_important = MemoryEntry(
        id="recent-less",
        type=MemoryType.EPISODIC,
        content="Quick database query tip",
        timestamp=now - timedelta(hours=1),
        importance=0.4,  # Less important
    )

    await memory_store.store(old_important)
    await memory_store.store(recent_less_important)

    # Search for "database"
    results = await memory_store.retrieve("database")

    # Old but very important should still rank first
    assert len(results) >= 2
    assert results[0].id == "old-important", "Very important memory should outweigh recency"


@pytest.mark.asyncio
async def test_profile_storage_empty(memory_store: SQLiteMemoryStore):
    """Test getting profile when none exists."""
    profile = await memory_store.get_profile()
    assert profile is None


@pytest.mark.asyncio
async def test_profile_storage_basic(memory_store: SQLiteMemoryStore):
    """Test storing and retrieving profile."""
    original = UserProfile(
        name="TestUser",
        timezone="UTC-8",
        interests=["Python", "AI"],
        preferences={"theme": "dark"},
    )

    await memory_store.update_profile(original)

    retrieved = await memory_store.get_profile()
    assert retrieved is not None
    assert retrieved.name == "TestUser"
    assert retrieved.timezone == "UTC-8"
    assert retrieved.interests == ["Python", "AI"]
    assert retrieved.preferences["theme"] == "dark"


@pytest.mark.asyncio
async def test_profile_storage_update(memory_store: SQLiteMemoryStore):
    """Test updating existing profile."""
    profile = UserProfile(name="Alice")
    await memory_store.update_profile(profile)

    # Update profile
    profile.add_interest("Machine Learning")
    profile.set_preference("code_style", "functional")
    await memory_store.update_profile(profile)

    # Retrieve and verify
    retrieved = await memory_store.get_profile()
    assert retrieved is not None
    assert "Machine Learning" in retrieved.interests
    assert retrieved.get_preference("code_style") == "functional"


@pytest.mark.asyncio
async def test_profile_migration_from_legacy(memory_store: SQLiteMemoryStore):
    """Test migrating from legacy user_name/user_context."""
    # Set legacy keys
    await memory_store.set_core("user_name", "LegacyUser")
    await memory_store.set_core("user_context", "Prefers concise responses")

    # Get profile should migrate
    profile = await memory_store.get_profile()
    assert profile is not None
    assert profile.name == "LegacyUser"
    assert profile.context == "Prefers concise responses"

    # Verify structured profile was saved
    profile_json = await memory_store.get_core("user_profile")
    assert profile_json is not None
