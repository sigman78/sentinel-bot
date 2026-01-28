"""Tests for memory store."""

from datetime import datetime
from pathlib import Path

import pytest

from sentinel.memory.base import MemoryEntry, MemoryType
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
