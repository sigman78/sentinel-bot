# Memory System

## Hierarchy

| Layer | Scope | Storage | Lifespan | Content |
|-------|-------|---------|----------|---------|
| Working | Session | In-memory | Session duration | Current conversation, active task state |
| Episodic | All interactions | SQLite | Permanent (compressed) | Timestamped conversation summaries, events |
| Semantic | Extracted facts | SQLite | Until contradicted | Factual statements, learned preferences |
| User Profile | User model | SQLite + JSON | Persistent, evolving | Preferences, communication style, relationships |
| World Model | External environment | JSON + SQLite | Persistent | Tool capabilities, integrations |

## Schemas

### Episodes Table
```sql
CREATE TABLE episodes (
    id TEXT PRIMARY KEY,
    timestamp DATETIME,
    summary TEXT,
    participants TEXT,  -- JSON array
    tags TEXT,          -- JSON array
    raw_hash TEXT,      -- Reference to full content if stored
    importance REAL     -- 0-1 score for retrieval ranking
);
```

### Facts Table
```sql
CREATE TABLE facts (
    id TEXT PRIMARY KEY,
    content TEXT,
    source_episode TEXT,
    confidence REAL,
    created DATETIME,
    last_verified DATETIME,
    superseded_by TEXT  -- NULL if current
);
```

### User Profile Structure
```python
@dataclass
class UserProfile:
    name: str
    preferences: dict[str, Any]      # UI, communication style
    schedule: dict                    # Work hours, timezone
    relationships: list[Relationship] # Known people
    interests: list[str]
    communication_style: str          # Formal, casual, etc.
    environment: str                  # personal, work
```

## Retrieval

**Pipeline**: Query → Keyword extraction → Relevance search → Ranking → Top-K results

| Method | Description |
|--------|-------------|
| Keyword | SQLite FTS5 full-text search |
| Temporal | Recent memories weighted higher |
| Importance | Pre-scored importance ranking |
| Tag-based | Filter by category |

Future: Vector embeddings for semantic search (when scale demands).

### Retrieval Triggers
- User message arrives → Retrieve relevant context
- Agent spawns → Load relevant memories for task
- Periodic → Awareness agent scans for relevant pending items

## Consolidation (Sleep Agent)

Process:
1. Scan recent episodic memories
2. Extract factual claims → Semantic memory
3. Update user profile if new preferences detected
4. Compress verbose episodes into summaries
5. Adjust importance scores based on recency/access

Schedule: Run during detected idle periods or low-activity hours.

## Storage Layout

- `data/sentinel.db` - Main SQLite database
- `data/episodes/{date}/{episode_id}.json` - Full conversation logs (optional)
- `data/user_profile.json` - Current user profile snapshot
- `data/world_model/tools.json` - Available tool definitions
- `data/world_model/integrations/` - Per-integration configs
