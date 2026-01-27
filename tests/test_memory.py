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
