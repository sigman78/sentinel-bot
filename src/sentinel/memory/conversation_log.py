"""Persistent conversation logging for memory migration.

This module provides structured logging of user-agent conversations
in a format that can be re-ingested by future memory implementations.

Storage format: Line-delimited JSON (NDJSON) files, rotated daily.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from sentinel.core.logging import get_logger
from sentinel.core.types import ContentType, Message

logger = get_logger("memory.conversation_log")

# Schema version for migration compatibility
SCHEMA_VERSION = "1.0.0"


class ConversationRole(Enum):
    """Role in a conversation exchange."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class ConversationEntry:
    """Single conversation entry with full metadata.

    This is the core data structure for persistent conversation storage.
    Designed to be forward-compatible with future memory systems.
    """

    id: str
    session_id: str
    timestamp: datetime
    role: ConversationRole
    content: str
    content_type: ContentType = ContentType.TEXT
    exchange_id: str | None = None  # Links user msg to assistant response
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "role": self.role.value,
            "content": self.content,
            "content_type": self.content_type.value,
            "exchange_id": self.exchange_id,
            "metadata": self.metadata,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConversationEntry:
        """Create from dictionary (handles schema migrations)."""
        version = data.get("schema_version", "1.0.0")

        return cls(
            id=data["id"],
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            role=ConversationRole(data["role"]),
            content=data["content"],
            content_type=ContentType(data.get("content_type", "text")),
            exchange_id=data.get("exchange_id"),
            metadata=data.get("metadata", {}),
            schema_version=version,
        )

    @classmethod
    def from_message(
        cls,
        message: Message,
        session_id: str,
        exchange_id: str | None = None,
    ) -> ConversationEntry:
        """Create entry from a Message object."""
        return cls(
            id=message.id,
            session_id=session_id,
            timestamp=message.timestamp,
            role=ConversationRole(message.role),
            content=message.content,
            content_type=message.content_type,
            exchange_id=exchange_id,
            metadata=message.metadata.copy(),
        )


@dataclass
class SessionMetadata:
    """Metadata for a conversation session."""

    session_id: str
    started_at: datetime
    ended_at: datetime | None = None
    message_count: int = 0
    summary: str | None = None
    topics: list[str] = field(default_factory=list)
    importance_score: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "message_count": self.message_count,
            "summary": self.summary,
            "topics": self.topics,
            "importance_score": self.importance_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionMetadata:
        """Create from dictionary."""
        return cls(
            session_id=data["session_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            message_count=data.get("message_count", 0),
            summary=data.get("summary"),
            topics=data.get("topics", []),
            importance_score=data.get("importance_score", 0.5),
        )


class ConversationLogStore:
    """File-based conversation log storage with daily rotation.

    Stores conversations in line-delimited JSON (NDJSON) files,
    rotated daily for easy management and migration.
    """

    def __init__(self, log_dir: Path | None = None):
        from sentinel.core.config import get_settings

        settings = get_settings()
        self.log_dir = log_dir or settings.data_dir / "conversations"
        self._current_session: str | None = None
        self._session_metadata: SessionMetadata | None = None
        self._current_date: date | None = None
        self._current_file: Path | None = None

    async def connect(self) -> None:
        """Initialize log directory."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Conversation log directory: {self.log_dir}")

    async def close(self) -> None:
        """Close any active session."""
        if self._current_session:
            await self.end_session()

    def _get_log_file_for_date(self, dt: datetime) -> Path:
        """Get the log file path for a given date."""
        date_str = dt.strftime("%Y-%m-%d")
        return self.log_dir / f"conversations_{date_str}.jsonl"

    def _get_metadata_file(self) -> Path:
        """Get the session metadata file path."""
        return self.log_dir / "sessions.jsonl"

    def _ensure_file_handle(self, timestamp: datetime) -> Path:
        """Ensure we have an open file handle for the given timestamp."""
        entry_date = timestamp.date()

        if entry_date != self._current_date or self._current_file is None:
            # Date changed, update current file
            self._current_date = entry_date
            self._current_file = self._get_log_file_for_date(timestamp)

        assert self._current_file is not None, "Current file should be set"
        return self._current_file

    async def start_session(self, session_id: str | None = None) -> str:
        """Start a new conversation session.

        Args:
            session_id: Optional session ID (generated if not provided)

        Returns:
            Session ID
        """
        if self._current_session:
            await self.end_session()

        self._current_session = session_id or str(uuid4())
        now = datetime.now()
        self._session_metadata = SessionMetadata(
            session_id=self._current_session,
            started_at=now,
        )

        logger.debug(f"Started conversation session: {self._current_session}")
        return self._current_session

    async def end_session(
        self,
        summary: str | None = None,
        topics: list[str] | None = None,
        importance: float = 0.5,
    ) -> None:
        """End the current conversation session."""
        if not self._current_session or not self._session_metadata:
            return

        # Update metadata
        self._session_metadata.ended_at = datetime.now()
        self._session_metadata.summary = summary
        self._session_metadata.topics = topics or []
        self._session_metadata.importance_score = importance

        # Write session metadata to file
        metadata_file = self._get_metadata_file()
        with open(metadata_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(self._session_metadata.to_dict(), ensure_ascii=False) + "\n")

        logger.debug(
            f"Ended session {self._current_session} with "
            f"{self._session_metadata.message_count} messages"
        )

        self._current_session = None
        self._session_metadata = None

    async def log_entry(self, entry: ConversationEntry) -> str:
        """Log a conversation entry.

        Args:
            entry: The conversation entry to log

        Returns:
            Entry ID
        """
        if not self._current_session:
            await self.start_session()

        # Use current session ID
        from dataclasses import replace

        entry = replace(entry, session_id=self._current_session)
        entry_id = entry.id or str(uuid4())

        # Get the appropriate log file
        log_file = self._ensure_file_handle(entry.timestamp)

        # Append to file
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        # Update session metadata
        if self._session_metadata:
            self._session_metadata.message_count += 1

        return entry_id

    async def log_exchange(
        self,
        user_msg: Message,
        assistant_msg: Message,
        session_id: str | None = None,
    ) -> tuple[str, str]:
        """Log a user-assistant exchange as linked entries.

        Args:
            user_msg: User message
            assistant_msg: Assistant response
            session_id: Optional session ID (uses current if not provided)

        Returns:
            Tuple of (user_entry_id, assistant_entry_id)
        """
        if session_id:
            if session_id != self._current_session:
                await self.start_session(session_id)
        elif not self._current_session:
            await self.start_session()

        exchange_id = str(uuid4())

        # Ensure we have a session
        current_session = self._current_session
        if current_session is None:
            raise RuntimeError("Session must be initialized before logging exchange")

        # Log user message
        user_entry = ConversationEntry.from_message(user_msg, current_session, exchange_id)
        user_id = await self.log_entry(user_entry)

        # Log assistant response (linked to user message)
        assistant_entry = ConversationEntry.from_message(
            assistant_msg, current_session, exchange_id
        )
        assistant_id = await self.log_entry(assistant_entry)

        return user_id, assistant_id

    def _read_entries_from_file(self, file_path: Path) -> list[ConversationEntry]:
        """Read all entries from a log file."""
        entries = []
        if not file_path.exists():
            return entries

        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entries.append(ConversationEntry.from_dict(data))
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse entry in {file_path}: {e}")
                    continue

        return entries

    async def get_session_messages(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[ConversationEntry]:
        """Get all messages for a session.

        Args:
            session_id: Session ID
            limit: Optional limit

        Returns:
            List of conversation entries
        """
        entries = []

        # Read all log files and filter by session
        for log_file in sorted(self.log_dir.glob("conversations_*.jsonl")):
            file_entries = self._read_entries_from_file(log_file)
            for entry in file_entries:
                if entry.session_id == session_id:
                    entries.append(entry)

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)

        if limit:
            entries = entries[-limit:]

        return entries

    async def get_recent_sessions(
        self,
        limit: int = 10,
        include_active: bool = False,
    ) -> list[dict[str, Any]]:
        """Get recent conversation sessions.

        Args:
            limit: Number of sessions to return
            include_active: Whether to include ongoing sessions

        Returns:
            List of session metadata
        """
        sessions = []
        metadata_file = self._get_metadata_file()

        if metadata_file.exists():
            with open(metadata_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        sessions.append(data)
                    except json.JSONDecodeError:
                        continue

        # Filter out active session if needed
        if not include_active and self._current_session:
            sessions = [s for s in sessions if s["session_id"] != self._current_session]

        # Sort by started_at descending
        sessions.sort(key=lambda s: s.get("started_at", ""), reverse=True)

        return sessions[:limit]

    async def export_to_ndjson(
        self,
        output_path: Path | None = None,
        compress: bool = False,
        session_id: str | None = None,
    ) -> Path:
        """Export conversations to NDJSON format for migration.

        Args:
            output_path: Output file path (default: auto-generated)
            compress: Whether to gzip compress
            session_id: Export specific session (default: all)

        Returns:
            Path to exported file
        """
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            suffix = ".jsonl.gz" if compress else ".jsonl"
            output_path = self.log_dir / f"export_{timestamp}{suffix}"

        # Collect all entries
        entries = []
        for log_file in sorted(self.log_dir.glob("conversations_*.jsonl")):
            file_entries = self._read_entries_from_file(log_file)
            if session_id:
                file_entries = [e for e in file_entries if e.session_id == session_id]
            entries.extend(file_entries)

        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)

        # Write to output
        if compress:
            with gzip.open(output_path, "wt", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                for entry in entries:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

        logger.info(f"Exported {len(entries)} conversations to {output_path}")
        return output_path

    @staticmethod
    def import_from_ndjson(
        input_path: Path,
        callback: Any | None = None,
    ) -> list[ConversationEntry]:
        """Import conversations from NDJSON file.

        Args:
            input_path: Path to NDJSON file (can be .gz compressed)
            callback: Optional callback(entry) for each imported entry

        Returns:
            List of imported entries
        """
        entries = []

        open_fn = gzip.open if str(input_path).endswith(".gz") else open

        with open_fn(input_path, "rt", encoding="utf-8") as f:  # type: ignore
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    entry = ConversationEntry.from_dict(data)
                    entries.append(entry)

                    if callback:
                        callback(entry)

                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse line {line_num} in {input_path}: {e}")
                    continue

        logger.info(f"Imported {len(entries)} entries from {input_path}")
        return entries

    async def get_stats(self) -> dict[str, Any]:
        """Get conversation statistics."""
        stats = {
            "total_sessions": 0,
            "total_messages": 0,
            "active_session": self._current_session,
            "log_files": 0,
            "date_range": None,
        }

        # Count log files and entries
        log_files = list(self.log_dir.glob("conversations_*.jsonl"))
        stats["log_files"] = len(log_files)

        earliest = None
        latest = None

        for log_file in log_files:
            entries = self._read_entries_from_file(log_file)
            stats["total_messages"] += len(entries)

            if entries:
                file_earliest = min(e.timestamp for e in entries)
                file_latest = max(e.timestamp for e in entries)

                if earliest is None or file_earliest < earliest:
                    earliest = file_earliest
                if latest is None or file_latest > latest:
                    latest = file_latest

        # Count sessions
        metadata_file = self._get_metadata_file()
        if metadata_file.exists():
            with open(metadata_file, encoding="utf-8") as f:
                sessions = [line for line in f if line.strip()]
                stats["total_sessions"] = len(sessions)

        if earliest and latest:
            stats["date_range"] = {
                "earliest": earliest.isoformat(),
                "latest": latest.isoformat(),
            }

        return stats
