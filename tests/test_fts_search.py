"""Test FTS5 full-text search functionality."""

from datetime import datetime

import pytest

from sentinel.memory.base import MemoryEntry, MemoryType
from sentinel.memory.store import SQLiteMemoryStore


@pytest.fixture
async def memory_store(tmp_path):
    """Create a temporary memory store."""
    db_path = tmp_path / "test_fts.db"
    store = SQLiteMemoryStore(db_path)
    await store.connect()
    yield store
    await store.close()


@pytest.mark.asyncio
async def test_fts5_available(memory_store):
    """Check if FTS5 is available in SQLite."""
    async with memory_store.conn.execute(
        "SELECT * FROM pragma_compile_options WHERE compile_options LIKE '%FTS5%'"
    ) as cursor:
        result = await cursor.fetchone()
        assert result is not None, "FTS5 is not available in this SQLite build"


@pytest.mark.asyncio
async def test_fts_table_exists(memory_store):
    """Verify FTS5 virtual table was created."""
    async with memory_store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='memory_fts'"
    ) as cursor:
        result = await cursor.fetchone()
        assert result is not None, "memory_fts table does not exist"


@pytest.mark.asyncio
async def test_fts_triggers_exist(memory_store):
    """Verify FTS sync triggers were created."""
    async with memory_store.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='trigger' "
        "AND name IN ('episodes_ai', 'facts_ai')"
    ) as cursor:
        results = await cursor.fetchall()
        assert len(results) == 2, f"Expected 2 triggers, found {len(results)}"


@pytest.mark.asyncio
async def test_fts_search_episodic(memory_store):
    """Test FTS5 search on episodic memories."""
    # Insert test episodes
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="The user discussed implementing FTS5 full-text search",
            timestamp=datetime.now(),
        )
    )
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="The agent suggested using SQLite for persistent storage",
            timestamp=datetime.now(),
        )
    )
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="They talked about Python async programming patterns",
            timestamp=datetime.now(),
        )
    )

    # Search for FTS-related content
    results = await memory_store.retrieve("FTS5", memory_type=MemoryType.EPISODIC, limit=5)
    assert len(results) > 0, "FTS search returned no results"
    assert any("FTS5" in r.content for r in results), "Search didn't find FTS5 content"


@pytest.mark.asyncio
async def test_fts_search_semantic(memory_store):
    """Test FTS5 search on semantic facts."""
    # Insert test facts
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.SEMANTIC,
            content="User prefers Python for backend development",
            timestamp=datetime.now(),
        )
    )
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.SEMANTIC,
            content="The system uses Claude API for language processing",
            timestamp=datetime.now(),
        )
    )

    # Search for facts
    results = await memory_store.retrieve("Python", memory_type=MemoryType.SEMANTIC, limit=5)
    assert len(results) > 0, "FTS search on facts returned no results"
    assert any("Python" in r.content for r in results), "Search didn't find Python content"


@pytest.mark.asyncio
async def test_fts_search_multi_word(memory_store):
    """Test FTS5 search with multiple words."""
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="User wants to implement a feature using machine learning algorithms",
            timestamp=datetime.now(),
        )
    )

    # Multi-word search
    results = await memory_store.retrieve("machine learning", limit=5)
    assert len(results) > 0, "Multi-word search returned no results"


@pytest.mark.asyncio
async def test_fts_no_results_fallback(memory_store):
    """Test that searching non-existent terms returns empty list."""
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="This is a test memory",
            timestamp=datetime.now(),
        )
    )

    # Search for something that doesn't exist
    results = await memory_store.retrieve("nonexistenttermxyz123", limit=5)
    assert len(results) == 0, "Search for non-existent term should return empty"


@pytest.mark.asyncio
async def test_fts_trigger_population(memory_store):
    """Verify FTS table is populated by triggers when inserting data."""
    # Insert an episode
    episode = MemoryEntry(
        id="",
        type=MemoryType.EPISODIC,
        content="Test content for FTS trigger verification",
        timestamp=datetime.now(),
    )
    entry_id = await memory_store.store(episode)

    # Check that FTS table has the entry
    async with memory_store.conn.execute(
        "SELECT id, content, memory_type FROM memory_fts WHERE id = ?",
        (entry_id,),
    ) as cursor:
        result = await cursor.fetchone()
        assert result is not None, "FTS table was not populated by trigger"
        assert result[1] == episode.content, "FTS content doesn't match"
        assert result[2] == "episodic", "FTS memory_type doesn't match"


@pytest.mark.asyncio
async def test_fts_porter_stemming(memory_store):
    """Test that FTS5 porter tokenizer works for stemming."""
    await memory_store.store(
        MemoryEntry(
            id="",
            type=MemoryType.EPISODIC,
            content="The user is running multiple tests",
            timestamp=datetime.now(),
        )
    )

    # Search with different word form (test vs tests)
    results = await memory_store.retrieve("test", limit=5)
    assert len(results) > 0, "Porter stemming didn't find 'test' from 'tests'"
