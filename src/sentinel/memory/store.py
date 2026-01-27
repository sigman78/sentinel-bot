"""
SQLite-based memory store implementation.

Implements hierarchical memory with FTS5 full-text search.
Borrowed concept from Letta: self-editing core memory blocks.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from sentinel.core.logging import get_logger
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType

logger = get_logger("memory.store")

SCHEMA = """
-- Core memory: agent-editable blocks (Letta concept)
CREATE TABLE IF NOT EXISTS core_memory (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Episodic memory: conversation summaries and events
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    summary TEXT NOT NULL,
    tags TEXT,  -- JSON array
    importance REAL DEFAULT 0.5,
    metadata TEXT  -- JSON object
);

-- Semantic memory: extracted facts
CREATE TABLE IF NOT EXISTS facts (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source_episode TEXT,
    confidence REAL DEFAULT 0.8,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    superseded_by TEXT
);

-- FTS5 index for full-text search
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    id,
    content,
    memory_type,
    content='',
    tokenize='porter'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO memory_fts(id, content, memory_type) VALUES (new.id, new.summary, 'episodic');
END;

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO memory_fts(id, content, memory_type) VALUES (new.id, new.content, 'semantic');
END;
"""


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory store with FTS5 search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info(f"Connected to memory store: {self.db_path}")

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Memory store not connected. Call connect() first.")
        return self._conn

    # Core memory operations (Letta-inspired self-editing blocks)

    async def get_core(self, key: str) -> str | None:
        """Get core memory value."""
        async with self.conn.execute(
            "SELECT value FROM core_memory WHERE key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set_core(self, key: str, value: str) -> None:
        """Set core memory value (agent-editable)."""
        await self.conn.execute(
            """INSERT INTO core_memory (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?""",
            (key, value, datetime.now(), value, datetime.now()),
        )
        await self.conn.commit()

    # Standard memory operations

    async def store(self, entry: MemoryEntry) -> str:
        """Store memory entry."""
        entry_id = entry.id or str(uuid4())

        if entry.type == MemoryType.EPISODIC:
            await self.conn.execute(
                """INSERT INTO episodes (id, timestamp, summary, tags, importance, metadata)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    entry_id,
                    entry.timestamp,
                    entry.content,
                    json.dumps(entry.tags) if entry.tags else None,
                    entry.importance,
                    json.dumps(entry.metadata) if entry.metadata else None,
                ),
            )
        elif entry.type == MemoryType.SEMANTIC:
            await self.conn.execute(
                """INSERT INTO facts (id, content, confidence, created_at)
                   VALUES (?, ?, ?, ?)""",
                (entry_id, entry.content, entry.importance, entry.timestamp),
            )

        await self.conn.commit()
        return entry_id

    async def retrieve(
        self,
        query: str,
        memory_type: MemoryType | None = None,
        limit: int = 10,
    ) -> list[MemoryEntry]:
        """Retrieve relevant memories using FTS5 search."""
        # Build FTS query
        type_filter = ""
        if memory_type:
            type_filter = f"AND memory_type = '{memory_type.value}'"

        sql = f"""
            SELECT id, content, memory_type
            FROM memory_fts
            WHERE memory_fts MATCH ? {type_filter}
            ORDER BY rank
            LIMIT ?
        """

        results = []
        try:
            async with self.conn.execute(sql, (query, limit)) as cursor:
                async for row in cursor:
                    results.append(
                        MemoryEntry(
                            id=row[0],
                            type=MemoryType(row[2]),
                            content=row[1],
                            timestamp=datetime.now(),  # FTS doesn't store timestamp
                        )
                    )
        except Exception as e:
            logger.debug(f"FTS search failed, falling back to LIKE: {e}")
            # Fallback to simple LIKE search
            results = await self._fallback_search(query, memory_type, limit)

        return results

    async def _fallback_search(
        self, query: str, memory_type: MemoryType | None, limit: int
    ) -> list[MemoryEntry]:
        """Simple LIKE search when FTS fails."""
        results = []
        pattern = f"%{query}%"

        if memory_type is None or memory_type == MemoryType.EPISODIC:
            async with self.conn.execute(
                "SELECT id, timestamp, summary FROM episodes WHERE summary LIKE ? LIMIT ?",
                (pattern, limit),
            ) as cursor:
                async for row in cursor:
                    results.append(
                        MemoryEntry(
                            id=row[0],
                            type=MemoryType.EPISODIC,
                            content=row[2],
                            timestamp=datetime.fromisoformat(row[1]) if row[1] else datetime.now(),
                        )
                    )

        if memory_type is None or memory_type == MemoryType.SEMANTIC:
            async with self.conn.execute(
                "SELECT id, created_at, content FROM facts WHERE content LIKE ? LIMIT ?",
                (pattern, limit),
            ) as cursor:
                async for row in cursor:
                    results.append(
                        MemoryEntry(
                            id=row[0],
                            type=MemoryType.SEMANTIC,
                            content=row[2],
                            timestamp=datetime.fromisoformat(row[1]) if row[1] else datetime.now(),
                        )
                    )

        return results[:limit]

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Get specific memory by ID."""
        # Check episodes
        async with self.conn.execute(
            "SELECT id, timestamp, summary, importance FROM episodes WHERE id = ?",
            (memory_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return MemoryEntry(
                    id=row[0],
                    type=MemoryType.EPISODIC,
                    content=row[2],
                    timestamp=datetime.fromisoformat(row[1]),
                    importance=row[3],
                )

        # Check facts
        async with self.conn.execute(
            "SELECT id, created_at, content, confidence FROM facts WHERE id = ?",
            (memory_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return MemoryEntry(
                    id=row[0],
                    type=MemoryType.SEMANTIC,
                    content=row[2],
                    timestamp=datetime.fromisoformat(row[1]),
                    importance=row[3],
                )

        return None

    async def update(self, memory_id: str, **fields: Any) -> bool:
        """Update memory fields."""
        # Simplified - only handle common updates
        if "importance" in fields:
            await self.conn.execute(
                "UPDATE episodes SET importance = ? WHERE id = ?",
                (fields["importance"], memory_id),
            )
            await self.conn.execute(
                "UPDATE facts SET confidence = ? WHERE id = ?",
                (fields["importance"], memory_id),
            )
            await self.conn.commit()
            return True
        return False

    async def delete(self, memory_id: str) -> bool:
        """Delete memory."""
        await self.conn.execute("DELETE FROM episodes WHERE id = ?", (memory_id,))
        await self.conn.execute("DELETE FROM facts WHERE id = ?", (memory_id,))
        await self.conn.execute("DELETE FROM memory_fts WHERE id = ?", (memory_id,))
        await self.conn.commit()
        return True
