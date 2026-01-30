"""Tests for /memory command functionality."""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from sentinel.interfaces.telegram import TelegramInterface
from sentinel.memory.base import MemoryEntry, MemoryType
from sentinel.memory.profile import UserProfile
from sentinel.memory.store import SQLiteMemoryStore


@pytest.mark.asyncio
async def test_memory_command_empty_memory(tmp_path: Path):
    """Test /memory command with empty memory."""
    memory = SQLiteMemoryStore(tmp_path / "test.db")
    await memory.connect()

    # Create minimal TelegramInterface instance for testing
    interface = TelegramInterface.__new__(TelegramInterface)
    interface.memory = memory
    interface.agent = None

    # Gather stats (simulating what _handle_memory does)
    episodic_count = 0
    async with memory.conn.execute("SELECT COUNT(*) FROM episodes") as cursor:
        row = await cursor.fetchone()
        episodic_count = row[0] if row else 0

    semantic_count = 0
    async with memory.conn.execute(
        "SELECT COUNT(*) FROM facts WHERE superseded_by IS NULL"
    ) as cursor:
        row = await cursor.fetchone()
        semantic_count = row[0] if row else 0

    assert episodic_count == 0
    assert semantic_count == 0

    await memory.close()


@pytest.mark.asyncio
async def test_memory_command_with_data(tmp_path: Path):
    """Test /memory command with actual memory data."""
    memory = SQLiteMemoryStore(tmp_path / "test.db")
    await memory.connect()

    # Add some episodic memories
    for i in range(3):
        entry = MemoryEntry(
            id=f"ep-{i}",
            type=MemoryType.EPISODIC,
            content=f"Test conversation {i}",
            timestamp=datetime.now() - timedelta(hours=i),
            importance=0.5,
        )
        await memory.store(entry)

    # Add some facts
    for i in range(2):
        entry = MemoryEntry(
            id=f"fact-{i}",
            type=MemoryType.SEMANTIC,
            content=f"Test fact {i}",
            timestamp=datetime.now(),
            importance=0.7,
        )
        await memory.store(entry)

    # Add user profile
    profile = UserProfile(
        name="TestUser",
        timezone="UTC-8",
        interests=["Python", "AI"],
        preferences={"theme": "dark"},
    )
    await memory.update_profile(profile)

    # Gather stats
    episodic_count = 0
    async with memory.conn.execute("SELECT COUNT(*) FROM episodes") as cursor:
        row = await cursor.fetchone()
        episodic_count = row[0] if row else 0

    semantic_count = 0
    async with memory.conn.execute(
        "SELECT COUNT(*) FROM facts WHERE superseded_by IS NULL"
    ) as cursor:
        row = await cursor.fetchone()
        semantic_count = row[0] if row else 0

    # Get recent memories (last 24h)
    recent_memories = []
    yesterday = datetime.now() - timedelta(days=1)
    async with memory.conn.execute(
        "SELECT summary, timestamp FROM episodes "
        "WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 5",
        (yesterday,),
    ) as cursor:
        async for row in cursor:
            recent_memories.append({"content": row[0], "timestamp": row[1]})

    # Get profile
    loaded_profile = await memory.get_profile()

    # Assertions
    assert episodic_count == 3
    assert semantic_count == 2
    assert len(recent_memories) == 3
    assert loaded_profile is not None
    assert loaded_profile.name == "TestUser"
    assert "Python" in loaded_profile.interests

    await memory.close()


@pytest.mark.asyncio
async def test_memory_command_recent_filter(tmp_path: Path):
    """Test that /memory only shows recent memories (last 24h)."""
    memory = SQLiteMemoryStore(tmp_path / "test.db")
    await memory.connect()

    # Add old memory (> 24h)
    old_entry = MemoryEntry(
        id="old",
        type=MemoryType.EPISODIC,
        content="Old conversation",
        timestamp=datetime.now() - timedelta(days=2),
        importance=0.5,
    )
    await memory.store(old_entry)

    # Add recent memory (< 24h)
    recent_entry = MemoryEntry(
        id="recent",
        type=MemoryType.EPISODIC,
        content="Recent conversation",
        timestamp=datetime.now() - timedelta(hours=2),
        importance=0.5,
    )
    await memory.store(recent_entry)

    # Get recent memories (last 24h)
    recent_memories = []
    yesterday = datetime.now() - timedelta(days=1)
    async with memory.conn.execute(
        "SELECT summary, timestamp FROM episodes "
        "WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 5",
        (yesterday,),
    ) as cursor:
        async for row in cursor:
            recent_memories.append({"content": row[0], "timestamp": row[1]})

    # Should only get recent memory
    assert len(recent_memories) == 1
    assert recent_memories[0]["content"] == "Recent conversation"

    await memory.close()
