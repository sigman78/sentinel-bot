"""SQLite memory store with FTS5 search and Letta-inspired core memory blocks."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import aiosqlite

from sentinel.core.logging import get_logger
from sentinel.memory.base import MemoryEntry, MemoryStore, MemoryType

logger = get_logger("memory.store")


# Python 3.12+ fix: Register datetime adapters explicitly
def _adapt_datetime(dt: datetime) -> str:
    """Convert datetime to ISO format string for SQLite storage."""
    return dt.isoformat()


def _convert_datetime(val: bytes) -> datetime:
    """Convert ISO format string from SQLite to datetime."""
    return datetime.fromisoformat(val.decode())


# Register adapters/converters to avoid Python 3.12 deprecation warning
sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("DATETIME", _convert_datetime)

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
    id UNINDEXED,
    content,
    memory_type UNINDEXED,
    tokenize='porter'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS episodes_ai AFTER INSERT ON episodes BEGIN
    INSERT INTO memory_fts(id, content, memory_type) VALUES (new.id, new.summary, 'episodic');
END;

CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO memory_fts(id, content, memory_type) VALUES (new.id, new.content, 'semantic');
END;

-- Scheduled tasks
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    description TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    schedule_data TEXT NOT NULL,
    execution_data TEXT,
    enabled INTEGER DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_run DATETIME,
    next_run DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run
    ON scheduled_tasks(next_run) WHERE enabled = 1;
"""


class SQLiteMemoryStore(MemoryStore):
    """SQLite-backed memory store with FTS5 search."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Initialize database connection and schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Use detect_types to enable our custom datetime converters
        self._conn = await aiosqlite.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
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
        results = []
        try:
            # Build type filter for FTS query
            type_filter = ""
            if memory_type:
                type_filter = f" AND memory_type = '{memory_type.value}'"

            # Search FTS5 table (now stores content directly)
            sql = f"""
                SELECT id, content, memory_type
                FROM memory_fts
                WHERE content MATCH ? {type_filter}
                ORDER BY rank
                LIMIT ?
            """

            async with self.conn.execute(sql, (query, limit)) as cursor:
                async for row in cursor:
                    entry_id = row[0]
                    entry_type = MemoryType(row[2])

                    # Fetch full details from source table
                    if entry_type == MemoryType.EPISODIC:
                        full_entry = await self.get(entry_id)
                        if full_entry:
                            results.append(full_entry)
                    elif entry_type == MemoryType.SEMANTIC:
                        full_entry = await self.get(entry_id)
                        if full_entry:
                            results.append(full_entry)

            logger.debug(f"FTS search returned {len(results)} results for query: {query}")

        except Exception as e:
            logger.warning(f"FTS search failed, falling back to LIKE: {e}")
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
                            timestamp=row[1] if row[1] else datetime.now(),
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
                            timestamp=row[1] if row[1] else datetime.now(),
                        )
                    )

        return results[:limit]

    async def get(self, memory_id: str) -> MemoryEntry | None:
        """Get specific memory by ID."""
        # Check episodes
        async with self.conn.execute(
            "SELECT id, timestamp, summary, importance, tags, metadata FROM episodes WHERE id = ?",
            (memory_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return MemoryEntry(
                    id=row[0],
                    type=MemoryType.EPISODIC,
                    content=row[2],
                    timestamp=row[1],
                    importance=row[3],
                    tags=json.loads(row[4]) if row[4] else None,
                    metadata=json.loads(row[5]) if row[5] else None,
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
                    timestamp=row[1],
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

    async def get_recent(self, limit: int = 10) -> list[MemoryEntry]:
        """Get most recent memories (fallback when search returns empty)."""
        results = []
        async with self.conn.execute(
            "SELECT id, timestamp, summary, importance, tags, metadata FROM episodes "
            "ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            async for row in cursor:
                results.append(
                    MemoryEntry(
                        id=row[0],
                        type=MemoryType.EPISODIC,
                        content=row[2],
                        timestamp=row[1] if row[1] else datetime.now(),
                        importance=row[3],
                        tags=json.loads(row[4]) if row[4] else None,
                        metadata=json.loads(row[5]) if row[5] else None,
                    )
                )
        return results

    # Task management operations

    async def create_task(
        self,
        task_id: str,
        task_type: str,
        description: str,
        schedule_type: str,
        schedule_data: dict,
        execution_data: dict | None,
        next_run: datetime,
    ) -> None:
        """Create a new scheduled task."""
        await self.conn.execute(
            """INSERT INTO scheduled_tasks
               (id, task_type, description, schedule_type, schedule_data,
                execution_data, enabled, created_at, next_run)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (
                task_id,
                task_type,
                description,
                schedule_type,
                json.dumps(schedule_data),
                json.dumps(execution_data) if execution_data else None,
                datetime.now(),
                next_run,
            ),
        )
        await self.conn.commit()

    async def get_task(self, task_id: str) -> dict | None:
        """Get task by ID."""
        async with self.conn.execute(
            """SELECT id, task_type, description, schedule_type, schedule_data,
                      execution_data, enabled, created_at, last_run, next_run
               FROM scheduled_tasks WHERE id = ?""",
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "task_type": row[1],
                    "description": row[2],
                    "schedule_type": row[3],
                    "schedule_data": json.loads(row[4]),
                    "execution_data": json.loads(row[5]) if row[5] else None,
                    "enabled": bool(row[6]),
                    "created_at": row[7],
                    "last_run": row[8],
                    "next_run": row[9],
                }
        return None

    async def list_tasks(self, enabled_only: bool = True) -> list[dict]:
        """List all tasks."""
        query = "SELECT id, task_type, description, schedule_type, schedule_data, execution_data, enabled, created_at, last_run, next_run FROM scheduled_tasks"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY next_run"

        results = []
        async with self.conn.execute(query) as cursor:
            async for row in cursor:
                results.append(
                    {
                        "id": row[0],
                        "task_type": row[1],
                        "description": row[2],
                        "schedule_type": row[3],
                        "schedule_data": json.loads(row[4]),
                        "execution_data": json.loads(row[5]) if row[5] else None,
                        "enabled": bool(row[6]),
                        "created_at": row[7],
                        "last_run": row[8],
                        "next_run": row[9],
                    }
                )
        return results

    async def get_due_tasks(self, now: datetime) -> list[dict]:
        """Get tasks that are due to run."""
        async with self.conn.execute(
            """SELECT id, task_type, description, schedule_type, schedule_data,
                      execution_data, enabled, created_at, last_run, next_run
               FROM scheduled_tasks
               WHERE enabled = 1 AND next_run <= ?
               ORDER BY next_run""",
            (now,),
        ) as cursor:
            results = []
            async for row in cursor:
                results.append(
                    {
                        "id": row[0],
                        "task_type": row[1],
                        "description": row[2],
                        "schedule_type": row[3],
                        "schedule_data": json.loads(row[4]),
                        "execution_data": json.loads(row[5]) if row[5] else None,
                        "enabled": bool(row[6]),
                        "created_at": row[7],
                        "last_run": row[8],
                        "next_run": row[9],
                    }
                )
        return results

    async def update_task(self, task_id: str, **fields: Any) -> bool:
        """Update task fields."""
        allowed_fields = ["enabled", "last_run", "next_run", "description"]
        updates = []
        values = []

        for key, value in fields.items():
            if key in allowed_fields:
                updates.append(f"{key} = ?")
                values.append(value)

        if not updates:
            return False

        values.append(task_id)
        sql = f"UPDATE scheduled_tasks SET {', '.join(updates)} WHERE id = ?"
        await self.conn.execute(sql, values)
        await self.conn.commit()
        return True

    async def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        await self.conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
        await self.conn.commit()
        return True
