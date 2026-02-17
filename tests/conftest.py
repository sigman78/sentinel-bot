"""Shared pytest fixtures for Sentinel tests."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from sentinel.memory.conversation_log import ConversationLogStore


@pytest.fixture
async def conversation_log():
    """Create temporary conversation log store for testing.

    This fixture provides an isolated ConversationLogStore that writes
    to a temporary directory, ensuring tests don't contaminate the
    production data/conversations/ directory.
    """
    with TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir) / "conversations"
        store = ConversationLogStore(log_dir)
        await store.connect()
        yield store
        await store.close()
