"""Tests for SleepAgent episode consolidation."""

from datetime import datetime, timedelta

from sentinel.agents.sleep import SleepAgent
from sentinel.memory.base import MemoryEntry, MemoryType


def test_group_similar_memories_no_similarity():
    """Test that dissimilar memories are not grouped."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    memories = [
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="Discussion about Python programming",
            timestamp=datetime.now(),
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="Weather conversation and travel plans",
            timestamp=datetime.now(),
            importance=0.5,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # No similarity, should get empty groups
    assert len(groups) == 0, "Dissimilar memories should not be grouped"


def test_group_similar_memories_high_overlap():
    """Test that similar memories are grouped together."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    memories = [
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="User asked about Python async programming patterns",
            timestamp=datetime.now(),
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="User asked about Python async programming best practices",
            timestamp=datetime.now() - timedelta(hours=2),
            importance=0.6,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # High similarity, should be grouped
    assert len(groups) == 1, "Similar memories should be grouped"
    assert len(groups[0]) == 2, "Group should contain both memories"
    assert {m.id for m in groups[0]} == {"1", "2"}


def test_group_similar_memories_time_window():
    """Test that only memories within time window are grouped."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    now = datetime.now()

    memories = [
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="Python async programming discussion today",
            timestamp=now,
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="Python async programming discussion old",
            timestamp=now - timedelta(days=10),  # Outside window
            importance=0.6,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # Similar but outside time window, should not be grouped
    assert len(groups) == 0, "Memories outside time window should not be grouped"


def test_group_similar_memories_multiple_groups():
    """Test that multiple distinct groups are identified."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    now = datetime.now()

    memories = [
        # Group 1: Python async discussions (high overlap)
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="User asked about Python async programming async patterns",
            timestamp=now,
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="User asked about Python async programming async examples",
            timestamp=now - timedelta(hours=1),
            importance=0.6,
        ),
        # Group 2: Database discussions (high overlap)
        MemoryEntry(
            id="3",
            type=MemoryType.EPISODIC,
            content="Discussion about database schema design database optimization",
            timestamp=now - timedelta(hours=3),
            importance=0.5,
        ),
        MemoryEntry(
            id="4",
            type=MemoryType.EPISODIC,
            content="Discussion about database schema indexing database queries",
            timestamp=now - timedelta(hours=4),
            importance=0.6,
        ),
        # Singleton: Unrelated
        MemoryEntry(
            id="5",
            type=MemoryType.EPISODIC,
            content="Weather forecast and weekend travel plans",
            timestamp=now,
            importance=0.5,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # Should find 2 groups (Python and Database)
    assert len(groups) == 2, f"Should identify 2 groups, found {len(groups)}"

    # Verify group sizes
    group_sizes = sorted([len(g) for g in groups])
    assert group_sizes == [2, 2], "Both groups should have 2 memories"


def test_group_similar_memories_min_group_size():
    """Test that singleton memories are not returned as groups."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    memories = [
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="Unique discussion about quantum physics",
            timestamp=datetime.now(),
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="Another unique chat about cooking",
            timestamp=datetime.now(),
            importance=0.6,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # No similar memories, should get no groups
    assert len(groups) == 0, "Singleton memories should not form groups"


def test_group_similar_memories_keyword_threshold():
    """Test that similarity threshold (50%) is respected."""
    agent = SleepAgent.__new__(SleepAgent)
    agent._consolidation_window = timedelta(days=7)

    memories = [
        MemoryEntry(
            id="1",
            type=MemoryType.EPISODIC,
            content="Discussion about Python programming language features",
            timestamp=datetime.now(),
            importance=0.5,
        ),
        MemoryEntry(
            id="2",
            type=MemoryType.EPISODIC,
            content="Talk about programming",  # Only 1 shared word out of 5-6 total
            timestamp=datetime.now() - timedelta(hours=1),
            importance=0.6,
        ),
    ]

    groups = agent._group_similar_memories(memories)

    # Low similarity (<50%), should not be grouped
    assert len(groups) == 0, "Memories with <50% similarity should not be grouped"
