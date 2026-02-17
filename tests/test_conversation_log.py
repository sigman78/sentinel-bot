"""Tests for conversation logging system."""

import gzip
import json
from datetime import datetime
from pathlib import Path

import pytest

from sentinel.core.types import ContentType, Message
from sentinel.memory.conversation_log import (
    SCHEMA_VERSION,
    ConversationEntry,
    ConversationLogStore,
    ConversationRole,
)


@pytest.fixture
async def conversation_store(tmp_path: Path):
    """Create a temporary conversation log store."""
    log_dir = tmp_path / "conversations"
    store = ConversationLogStore(log_dir)
    await store.connect()
    yield store
    await store.close()


@pytest.fixture
def sample_message() -> Message:
    """Create a sample message."""
    return Message(
        id="msg-1",
        timestamp=datetime.now(),
        role="user",
        content="Hello, how are you?",
        content_type=ContentType.TEXT,
        metadata={"test": True},
    )


@pytest.fixture
def sample_response() -> Message:
    """Create a sample assistant response."""
    return Message(
        id="msg-2",
        timestamp=datetime.now(),
        role="assistant",
        content="I'm doing well, thank you!",
        content_type=ContentType.TEXT,
        metadata={"model": "claude", "cost_usd": 0.001},
    )


@pytest.mark.asyncio
async def test_conversation_entry_from_message(sample_message: Message):
    """Test creating ConversationEntry from Message."""
    entry = ConversationEntry.from_message(
        sample_message,
        session_id="session-1",
        exchange_id="ex-1",
    )

    assert entry.id == "msg-1"
    assert entry.session_id == "session-1"
    assert entry.exchange_id == "ex-1"
    assert entry.role == ConversationRole.USER
    assert entry.content == "Hello, how are you?"
    assert entry.content_type == ContentType.TEXT
    assert entry.metadata == {"test": True}


@pytest.mark.asyncio
async def test_conversation_entry_serialization(sample_message: Message):
    """Test serialization and deserialization."""
    entry = ConversationEntry.from_message(
        sample_message, session_id="session-1", exchange_id="ex-1"
    )

    # Serialize to dict
    data = entry.to_dict()

    assert data["id"] == "msg-1"
    assert data["session_id"] == "session-1"
    assert data["role"] == "user"
    assert data["content"] == "Hello, how are you?"
    assert data["schema_version"] == SCHEMA_VERSION

    # Deserialize from dict
    restored = ConversationEntry.from_dict(data)

    assert restored.id == entry.id
    assert restored.session_id == entry.session_id
    assert restored.role == entry.role
    assert restored.content == entry.content


@pytest.mark.asyncio
async def test_session_management(conversation_store: ConversationLogStore):
    """Test starting and ending sessions."""
    # Start a session
    session_id = await conversation_store.start_session()
    assert session_id is not None
    assert conversation_store._current_session == session_id

    # End the session
    await conversation_store.end_session(
        summary="Test session summary",
        topics=["testing", "memory"],
        importance=0.8,
    )
    assert conversation_store._current_session is None

    # Verify session was recorded
    sessions = await conversation_store.get_recent_sessions(include_active=True)
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == session_id
    assert sessions[0]["summary"] == "Test session summary"
    assert sessions[0]["importance_score"] == 0.8


@pytest.mark.asyncio
async def test_log_entry(conversation_store: ConversationLogStore):
    """Test logging a single entry."""
    await conversation_store.start_session()

    entry = ConversationEntry(
        id="entry-1",
        session_id="test-session",  # Will be overwritten
        timestamp=datetime.now(),
        role=ConversationRole.USER,
        content="Test message",
    )

    entry_id = await conversation_store.log_entry(entry)
    assert entry_id == "entry-1"

    # Verify entry was stored
    messages = await conversation_store.get_session_messages(conversation_store._current_session)
    assert len(messages) == 1
    assert messages[0].content == "Test message"


@pytest.mark.asyncio
async def test_log_exchange(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
):
    """Test logging a user-assistant exchange."""
    await conversation_store.start_session()

    user_id, assistant_id = await conversation_store.log_exchange(sample_message, sample_response)

    assert user_id == "msg-1"
    assert assistant_id == "msg-2"

    # Verify both messages were stored
    messages = await conversation_store.get_session_messages(conversation_store._current_session)
    assert len(messages) == 2

    # Verify exchange linking
    user_entry = next(m for m in messages if m.role == ConversationRole.USER)
    assistant_entry = next(m for m in messages if m.role == ConversationRole.ASSISTANT)
    assert user_entry.exchange_id == assistant_entry.exchange_id


@pytest.mark.asyncio
async def test_get_session_messages(conversation_store: ConversationLogStore):
    """Test retrieving session messages."""
    session_id = await conversation_store.start_session()

    # Log multiple messages
    for i in range(5):
        entry = ConversationEntry(
            id=f"entry-{i}",
            session_id=session_id,
            timestamp=datetime.now(),
            role=ConversationRole.USER if i % 2 == 0 else ConversationRole.ASSISTANT,
            content=f"Message {i}",
        )
        await conversation_store.log_entry(entry)

    # Get all messages
    messages = await conversation_store.get_session_messages(session_id)
    assert len(messages) == 5

    # Get with limit
    limited = await conversation_store.get_session_messages(session_id, limit=3)
    assert len(limited) == 3


@pytest.mark.asyncio
async def test_export_to_ndjson(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
    tmp_path: Path,
):
    """Test exporting conversations to NDJSON."""
    await conversation_store.start_session()
    await conversation_store.log_exchange(sample_message, sample_response)
    await conversation_store.end_session()

    # Export
    output_path = tmp_path / "export.jsonl"
    result = await conversation_store.export_to_ndjson(output_path, compress=False)

    assert result.exists()

    # Read and verify
    with open(result) as f:
        lines = f.readlines()

    assert len(lines) == 2

    # Parse entries
    entries = [json.loads(line) for line in lines]
    assert entries[0]["role"] == "user"
    assert entries[1]["role"] == "assistant"
    assert entries[0]["exchange_id"] == entries[1]["exchange_id"]


@pytest.mark.asyncio
async def test_export_to_ndjson_compressed(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
    tmp_path: Path,
):
    """Test exporting conversations to compressed NDJSON."""
    await conversation_store.start_session()
    await conversation_store.log_exchange(sample_message, sample_response)
    await conversation_store.end_session()

    # Export compressed
    output_path = tmp_path / "export.jsonl.gz"
    result = await conversation_store.export_to_ndjson(output_path, compress=True)

    assert result.exists()
    assert str(result).endswith(".gz")

    # Read and verify
    with gzip.open(result, "rt") as f:
        lines = f.readlines()

    assert len(lines) == 2


@pytest.mark.asyncio
async def test_import_from_ndjson(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
    tmp_path: Path,
):
    """Test importing conversations from NDJSON."""
    # Create export file
    entries = [
        ConversationEntry.from_message(sample_message, "session-1", "ex-1"),
        ConversationEntry.from_message(sample_response, "session-1", "ex-1"),
    ]

    export_path = tmp_path / "import.jsonl"
    with open(export_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry.to_dict()) + "\n")

    # Import
    imported = ConversationLogStore.import_from_ndjson(export_path)

    assert len(imported) == 2
    assert imported[0].role == ConversationRole.USER
    assert imported[1].role == ConversationRole.ASSISTANT


@pytest.mark.asyncio
async def test_import_from_ndjson_with_callback(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
    tmp_path: Path,
):
    """Test importing with callback."""
    entries = [
        ConversationEntry.from_message(sample_message, "session-1", "ex-1"),
        ConversationEntry.from_message(sample_response, "session-1", "ex-1"),
    ]

    export_path = tmp_path / "import.jsonl"
    with open(export_path, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry.to_dict()) + "\n")

    # Import with callback
    collected = []
    ConversationLogStore.import_from_ndjson(export_path, callback=lambda e: collected.append(e.id))

    assert len(collected) == 2
    assert collected[0] == "msg-1"
    assert collected[1] == "msg-2"


@pytest.mark.asyncio
async def test_get_stats(conversation_store: ConversationLogStore):
    """Test getting conversation statistics."""
    # Empty stats
    stats = await conversation_store.get_stats()
    assert stats["total_sessions"] == 0
    assert stats["total_messages"] == 0
    assert stats["log_files"] == 0

    # Add some data
    await conversation_store.start_session("session-1")
    for i in range(3):
        entry = ConversationEntry(
            id=f"entry-{i}",
            session_id="session-1",
            timestamp=datetime.now(),
            role=ConversationRole.USER,
            content=f"Message {i}",
        )
        await conversation_store.log_entry(entry)
    await conversation_store.end_session()

    # Get stats again
    stats = await conversation_store.get_stats()
    assert stats["total_sessions"] == 1
    assert stats["total_messages"] == 3
    assert stats["log_files"] == 1
    assert stats["date_range"] is not None


@pytest.mark.asyncio
async def test_multiple_sessions(conversation_store: ConversationLogStore):
    """Test handling multiple sessions."""
    # Session 1
    await conversation_store.start_session("session-1")
    entry = ConversationEntry(
        id="s1-msg",
        session_id="session-1",
        timestamp=datetime.now(),
        role=ConversationRole.USER,
        content="Session 1 message",
    )
    await conversation_store.log_entry(entry)
    await conversation_store.end_session()

    # Session 2
    await conversation_store.start_session("session-2")
    entry = ConversationEntry(
        id="s2-msg",
        session_id="session-2",
        timestamp=datetime.now(),
        role=ConversationRole.USER,
        content="Session 2 message",
    )
    await conversation_store.log_entry(entry)
    await conversation_store.end_session()

    # Verify sessions
    sessions = await conversation_store.get_recent_sessions()
    assert len(sessions) == 2

    # Verify session isolation
    s1_messages = await conversation_store.get_session_messages("session-1")
    assert len(s1_messages) == 1
    assert s1_messages[0].content == "Session 1 message"

    s2_messages = await conversation_store.get_session_messages("session-2")
    assert len(s2_messages) == 1
    assert s2_messages[0].content == "Session 2 message"


@pytest.mark.asyncio
async def test_export_specific_session(
    conversation_store: ConversationLogStore,
    sample_message: Message,
    sample_response: Message,
    tmp_path: Path,
):
    """Test exporting only a specific session."""
    # Session 1
    await conversation_store.start_session("session-1")
    await conversation_store.log_exchange(sample_message, sample_response)
    await conversation_store.end_session()

    # Session 2 - use new messages with different IDs
    msg3 = Message(
        id="msg-3",
        timestamp=datetime.now(),
        role="user",
        content="Hello again",
        content_type=ContentType.TEXT,
    )
    msg4 = Message(
        id="msg-4",
        timestamp=datetime.now(),
        role="assistant",
        content="Hi there!",
        content_type=ContentType.TEXT,
    )
    await conversation_store.start_session("session-2")
    await conversation_store.log_exchange(msg3, msg4)
    await conversation_store.end_session()

    # Export only session 1
    output_path = tmp_path / "session1_only.jsonl"
    result = await conversation_store.export_to_ndjson(
        output_path, compress=False, session_id="session-1"
    )

    # Read and verify
    with open(result) as f:
        lines = f.readlines()

    assert len(lines) == 2
    entries = [json.loads(line) for line in lines]
    assert all(e["session_id"] == "session-1" for e in entries)


@pytest.mark.asyncio
async def test_image_message_logging(conversation_store: ConversationLogStore):
    """Test logging image messages with metadata."""
    await conversation_store.start_session()

    image_message = Message(
        id="img-1",
        timestamp=datetime.now(),
        role="user",
        content="Check this image",
        content_type=ContentType.IMAGE,
        metadata={
            "images": [{"data": "base64data...", "media_type": "image/jpeg", "source": "telegram"}]
        },
    )

    entry = ConversationEntry.from_message(image_message, conversation_store._current_session)
    await conversation_store.log_entry(entry)

    messages = await conversation_store.get_session_messages(conversation_store._current_session)
    assert len(messages) == 1
    assert messages[0].content_type == ContentType.IMAGE
    assert "images" in messages[0].metadata


@pytest.mark.asyncio
async def test_daily_log_rotation(conversation_store: ConversationLogStore):
    """Test that logs are split by date."""

    # Log message for today
    await conversation_store.start_session()
    entry1 = ConversationEntry(
        id="today-msg",
        session_id=conversation_store._current_session,
        timestamp=datetime.now(),
        role=ConversationRole.USER,
        content="Today's message",
    )
    await conversation_store.log_entry(entry1)
    await conversation_store.end_session()

    # Check that a log file was created
    log_files = list(conversation_store.log_dir.glob("conversations_*.jsonl"))
    assert len(log_files) >= 1

    # Verify file naming
    today_file = conversation_store._get_log_file_for_date(datetime.now())
    assert today_file.exists()
