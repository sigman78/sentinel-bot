# Memory Subsystem Analysis

**Analysis Date**: 2026-01-28
**Status**: Phase 2 "Complete" - but with gaps

---

## Executive Summary

The memory system has solid foundations with a clean 3-tier hierarchy (working/episodic/semantic), FTS5 search, and core memory blocks. However, critical gaps exist:

**Missing Critical Features**:
- User profile layer (no structured preferences/relationships)
- Temporal/importance-based retrieval ranking
- Memory consolidation (incomplete - only fact extraction)
- World model persistence (tools/integrations)
- Episode compression and deduplication

**Strengths**:
- Clean abstract interface (MemoryStore ABC)
- FTS5 full-text search with proper escaping ✅
- Core memory blocks (Letta-inspired self-editing)
- Background consolidation infrastructure (SleepAgent)
- Proper SQLite schema with triggers for FTS sync

---

## Current Implementation

### 1. Memory Hierarchy (3/5 Layers Implemented)

| Layer | Status | Storage | Implementation Quality |
|-------|--------|---------|----------------------|
| **Working** | ✅ Implemented | In-memory (AgentContext.conversation) | Good - simple list, trimmed to max_history |
| **Episodic** | ⚠️ Partial | SQLite `episodes` table | Schema ready, but no compression/deduplication |
| **Semantic** | ⚠️ Partial | SQLite `facts` table | Basic storage works, but no fact updating/superseding |
| **User Profile** | ❌ Missing | Core memory (user_name, user_context only) | No structured profile, relationships, or schedule |
| **World Model** | ❌ Missing | Nothing | No tool definitions or integration configs |

### 2. Database Schema

**Implemented Tables**:

```sql
-- ✅ Core Memory (Letta-style editable blocks)
core_memory (key, value, updated_at)
  - Currently used: user_name, user_context
  - Missing: user_preferences, schedule, relationships, environment

-- ⚠️ Episodes (schema complete, features missing)
episodes (id, timestamp, summary, tags, importance, metadata)
  - Missing: participants field (from docs)
  - Missing: raw_hash (reference to full content)
  - No compression logic implemented
  - No deduplication

-- ⚠️ Facts (schema incomplete)
facts (id, content, source_episode, confidence, created_at, superseded_by)
  - Missing: last_verified field (from docs)
  - superseded_by field unused (no fact updating logic)
  - No confidence adjustment over time

-- ✅ FTS5 Search (working correctly)
memory_fts (id, content, memory_type)
  - Triggers keep FTS in sync automatically
  - Porter stemmer for better matching
  - Proper query escaping (fixed today)

-- ✅ Task Management (separate subsystem)
scheduled_tasks (complete and working)
```

**Schema Gaps vs Documentation**:
- Missing `participants` field in episodes (multi-user support)
- Missing `raw_hash` and full content storage path
- Missing `last_verified` in facts
- No separate user_profile or world_model tables

### 3. API Surface (MemoryStore ABC)

**Core Interface** (base.py:33-64):
```python
class MemoryStore(ABC):
    async def store(entry: MemoryEntry) -> str        # ✅ Works
    async def retrieve(query, type, limit) -> list    # ⚠️ No ranking
    async def get(memory_id) -> MemoryEntry           # ✅ Works
    async def update(memory_id, **fields) -> bool     # ⚠️ Limited fields
    async def delete(memory_id) -> bool               # ✅ Works
```

**SQLite Extensions** (store.py):
```python
# Core memory (Letta concept)
async def get_core(key) -> str                        # ✅ Works
async def set_core(key, value) -> None                # ✅ Works

# Fallback retrieval
async def get_recent(limit) -> list[MemoryEntry]      # ✅ Works

# Task management (integrated here - questionable)
async def create_task(...)                            # ✅ Works
async def get_task(task_id)                           # ✅ Works
async def list_tasks(enabled_only)                    # ✅ Works
async def get_due_tasks(now)                          # ✅ Works
async def update_task(task_id, **fields)              # ✅ Works
async def delete_task(task_id)                        # ✅ Works
```

**Missing Methods**:
- `retrieve_by_importance(threshold, limit)` - No importance-based retrieval
- `retrieve_by_timerange(start, end, limit)` - No temporal queries
- `retrieve_by_tags(tags, limit)` - Tags stored but never queried
- `update_importance(memory_id, score)` - No decay/boosting
- `supersede_fact(old_id, new_id)` - No fact versioning
- `get_user_profile() -> UserProfile` - No profile API
- `update_user_profile(**fields)` - No profile updates
- `consolidate_episodes(ids)` - No manual consolidation

---

## Memory Usage Patterns

### DialogAgent (Current Usage)

**On initialization**:
```python
# Load user profile from core memory
user_name = await memory.get_core("user_name")
user_context = await memory.get_core("user_context")
```

**On message processing**:
```python
# Retrieve relevant memories
memories = await memory.retrieve(query, limit=5)
if not memories:
    memories = await memory.get_recent(limit=5)  # Fallback

# Format and inject into system prompt
memory_text = self._format_memories(memories)
system_prompt = template.format(..., memories=memory_text)
```

**On session end**:
```python
# Store conversation summary as episodic memory
entry = MemoryEntry(
    id=uuid4(),
    type=MemoryType.EPISODIC,
    content=summary_text,
    timestamp=datetime.now(),
    importance=0.5,  # Fixed importance - no dynamic scoring
)
await memory.store(entry)
```

**Problems**:
- No importance calculation - always 0.5
- No tagging of episodes
- No participant tracking
- Retrieve doesn't rank by importance/recency
- Falls back to `get_recent()` when FTS returns empty

### SleepAgent (Background Consolidation)

**Current Implementation** (sleep.py:55-92):
```python
async def run_consolidation():
    # Get recent episodes
    recent = await memory.get_recent(limit=20)

    # Extract facts using LLM
    facts = await self._extract_facts(recent)

    # Store as semantic memory
    for fact in facts:
        entry = MemoryEntry(
            type=MemoryType.SEMANTIC,
            content=fact,
            importance=0.7,  # Fixed - no dynamic scoring
            metadata={"source": "sleep_consolidation"}
        )
        await memory.store(entry)
```

**Problems**:
- Only extracts facts, doesn't consolidate episodes
- No episode compression or deduplication
- No importance decay over time
- No fact superseding (old facts remain forever)
- `_consolidate_related()` method exists but never called
- No user profile updates from new preferences

---

## Ideal Memory System (Goals)

### 1. Retrieval Strategy

**Current**: Simple FTS5 keyword search + fallback to recent
**Ideal**: Multi-factor ranking system

```python
# Ideal retrieval API
memories = await memory.retrieve(
    query="user's coding preferences",
    strategy=RetrievalStrategy.HYBRID,  # FTS + importance + temporal
    weights={
        "relevance": 0.5,    # FTS5 score
        "importance": 0.3,   # Pre-scored importance
        "recency": 0.2,      # Time decay
    },
    limit=10
)
```

**Missing Components**:
- Importance-based ranking (importance field unused)
- Temporal decay (older memories should score lower)
- Tag-based filtering (tags stored but never used)
- Memory access tracking (frequently accessed = more important)
- Embedding-based semantic search (future - not needed yet)

### 2. Memory Consolidation

**Current**: Only fact extraction
**Ideal**: Multi-stage consolidation pipeline

```
Stage 1: Fact Extraction (✅ implemented)
  - LLM extracts durable facts from episodes
  - Stores as semantic memory

Stage 2: Episode Compression (❌ missing)
  - Identify similar/redundant episodes
  - Consolidate into single summary
  - Keep raw content separately with hash reference

Stage 3: Importance Adjustment (❌ missing)
  - Decay importance over time
  - Boost frequently accessed memories
  - Lower importance of superseded facts

Stage 4: Profile Updates (❌ missing)
  - Detect new preferences/habits
  - Update core memory profile blocks
  - Track relationship changes

Stage 5: Fact Versioning (❌ missing)
  - Detect contradictory facts
  - Mark old fact as superseded_by
  - Keep history for verification
```

### 3. User Profile Layer

**Current**: Two core memory keys (`user_name`, `user_context`)
**Ideal**: Structured profile with relationships

```python
@dataclass
class UserProfile:
    # Basic identity
    name: str
    timezone: str
    language: str

    # Preferences
    preferences: dict[str, Any]  # coding_style, notification_frequency, etc.
    communication_style: str     # formal, casual, technical
    environment: str             # personal, work, mobile

    # Schedule and availability
    work_hours: TimeRange
    sleep_schedule: TimeRange
    timezone_offset: int

    # Relationships (for multi-user)
    relationships: list[Relationship]  # friend, coworker, family

    # Interests and expertise
    interests: list[str]
    expertise_areas: list[str]
    learning_goals: list[str]
```

**Implementation Options**:
1. **JSON in core_memory**: Store as single `user_profile` key (simple)
2. **Separate table**: Better schema, queryable fields (recommended)
3. **Hybrid**: Critical fields in core_memory, extended data in table

### 4. World Model Layer

**Current**: Nothing
**Ideal**: Tool and integration state

```python
# World model stores:
- Available tool definitions and capabilities
- Integration configurations (API keys, endpoints)
- External system state (GitHub repos, calendars)
- Environment variables and paths
```

**Storage Options**:
- `data/world_model/tools.json` - Tool registry
- `data/world_model/integrations/` - Per-integration configs
- SQLite table for queryable state

---

## Critical Gaps and Issues

### 1. Retrieval Quality (HIGH PRIORITY)

**Problem**: `retrieve()` doesn't use importance or recency
```python
# Current implementation (store.py:211-219)
sql = """
    SELECT id, content, memory_type
    FROM memory_fts
    WHERE content MATCH ? {type_filter}
    ORDER BY rank                    # FTS5 rank only - no importance!
    LIMIT ?
"""
```

**Fix**: Join with source tables to access importance/timestamp
```python
# Proposed fix
sql = """
    SELECT fts.id, fts.content, fts.memory_type,
           COALESCE(e.importance, f.confidence) as importance,
           COALESCE(e.timestamp, f.created_at) as timestamp,
           fts.rank
    FROM memory_fts fts
    LEFT JOIN episodes e ON fts.id = e.id AND fts.memory_type = 'episodic'
    LEFT JOIN facts f ON fts.id = f.id AND fts.memory_type = 'semantic'
    WHERE content MATCH ? {type_filter}
    ORDER BY
        (rank * 0.5) +                    # FTS relevance
        (importance * 0.3) +              # Pre-scored importance
        (temporal_weight * 0.2) DESC      # Time decay
    LIMIT ?
"""
```

### 2. Memory Consolidation Incomplete (MEDIUM PRIORITY)

**Problem**: SleepAgent only extracts facts, doesn't consolidate episodes

**Missing**:
- Episode deduplication (same conversation summarized multiple times)
- Episode compression (merge related summaries)
- Importance decay (old memories less relevant)
- Fact superseding (update contradictory facts)

**Recommendation**: Implement `_consolidate_related()` in SleepAgent:
```python
async def run_consolidation():
    # Phase 1: Extract facts (✅ working)
    facts = await self._extract_facts(recent)

    # Phase 2: Consolidate episodes (❌ add this)
    similar_episodes = self._find_similar_episodes(recent)
    for group in similar_episodes:
        consolidated = await self._consolidate_related(group)
        # Store consolidated, mark originals as compressed

    # Phase 3: Decay importance (❌ add this)
    await self._decay_old_memories()

    # Phase 4: Update profile (❌ add this)
    await self._update_user_profile(facts)
```

### 3. User Profile Missing (MEDIUM PRIORITY)

**Problem**: Only `user_name` and `user_context` - no structured profile

**Recommendation**: Add proper profile layer
```python
# Option 1: JSON in core memory (quick)
await memory.set_core("user_profile", json.dumps({
    "name": "Alice",
    "preferences": {"code_style": "functional", "tz": "UTC-8"},
    "schedule": {"work_hours": "9am-5pm"},
    "interests": ["AI", "Python", "music"]
}))

# Option 2: Separate table (better)
CREATE TABLE user_profile (
    user_id TEXT PRIMARY KEY,  -- For multi-user support
    name TEXT,
    preferences TEXT,  -- JSON
    schedule TEXT,     -- JSON
    relationships TEXT,-- JSON
    interests TEXT,    -- JSON array
    updated_at DATETIME
);
```

### 4. Fact Versioning Unused (LOW PRIORITY)

**Problem**: `superseded_by` field exists but never set

**Recommendation**: Implement fact updating in SleepAgent:
```python
async def _check_fact_conflicts(new_facts: list[str]):
    for new_fact in new_facts:
        # Search for contradictory facts
        existing = await memory.retrieve(new_fact, type=MemoryType.SEMANTIC)

        for old_fact in existing:
            if self._is_contradiction(old_fact.content, new_fact):
                # Mark old fact as superseded
                await memory.update(
                    old_fact.id,
                    superseded_by=new_fact_id
                )
```

### 5. Tags Never Used (LOW PRIORITY)

**Problem**: Episodes have `tags` field, but never queried

**Recommendation**: Add tagging support
```python
# In DialogAgent.summarize_session()
tags = self._extract_tags(summary)  # "coding", "personal", "urgent"
entry = MemoryEntry(..., tags=tags)

# In retrieval
memories = await memory.retrieve_by_tags(["coding", "preferences"])
```

### 6. Metadata Underutilized (LOW PRIORITY)

**Problem**: `metadata` field exists but rarely populated

**Use Cases**:
- Source tracking (which conversation, which user)
- Confidence scores from LLM
- Access counters (for importance boosting)
- Compression history (original episode IDs)

---

## Recommended Priorities

### Immediate (Next Sprint)

1. **Fix retrieval ranking** - Join with source tables to use importance/timestamp
2. **Add importance calculation** - Dynamic scoring in DialogAgent.summarize_session()
3. **Implement episode consolidation** - Use existing `_consolidate_related()` method

### Short Term (Next Month)

4. **User profile layer** - JSON in core_memory first, migrate to table later
5. **Fact versioning** - Implement superseding logic in SleepAgent
6. **Importance decay** - Periodic background task to age memories

### Long Term (3-6 Months)

7. **World model layer** - Tool/integration state persistence
8. **Tag-based retrieval** - Full tag support with filtering
9. **Vector embeddings** - Semantic search when scale demands it
10. **Multi-user support** - User isolation and shared knowledge

---

## Architecture Assessment

### What Works Well

✅ **Clean Abstraction**: MemoryStore ABC allows swapping implementations
✅ **FTS5 Integration**: Full-text search with proper escaping
✅ **Core Memory Blocks**: Letta-inspired self-editing works well
✅ **Background Processing**: SleepAgent infrastructure solid
✅ **Schema Design**: Tables well-designed, triggers keep FTS in sync

### Design Issues

⚠️ **Task Management Coupling**: Tasks in MemoryStore feels wrong
  - Tasks are operational, not memory
  - Recommendation: Move to separate `TaskStore` class

⚠️ **No Retrieval Strategy Pattern**: Hard-coded FTS + fallback
  - Recommendation: Strategy pattern for different retrieval modes

⚠️ **Fixed Importance Scores**: Always 0.5 or 0.7
  - Recommendation: Dynamic importance calculation

⚠️ **No Memory Lifecycle**: Memories never age or compress
  - Recommendation: Add lifecycle management to SleepAgent

### Missing Abstractions

❌ **UserProfile Class**: Should be first-class entity, not dict
❌ **RetrievalStrategy**: Pluggable retrieval modes
❌ **MemoryConsolidator**: Separate from SleepAgent
❌ **ImportanceScorer**: Centralized scoring logic

---

## Comparison to Ideal Systems

### Letta (MemGPT) Inspiration

**What we adopted** ✅:
- Core memory blocks (self-editing)
- Working/episodic/semantic hierarchy

**What we're missing** ❌:
- Archival memory (long-term compressed storage)
- Memory pagination (loading memories in chunks)
- Memory metadata tracking (access counts, importance)

### LangChain Memory

**Better than LangChain** ✅:
- Proper SQLite with FTS5 (LangChain uses simple lists)
- Background consolidation (LangChain is passive)
- Core memory concept (LangChain lacks self-editing)

**Missing from LangChain** ❌:
- Vector store integration (we don't need it yet)
- Conversation buffer strategies (our trimming is naive)

### Production AI Assistants

**On Par** ✅:
- Persistent conversation memory
- Full-text search
- Session summarization

**Missing** ❌:
- User profile inference from behavior
- Proactive memory updates (we're close with SleepAgent)
- Multi-session context (we only look at recent)
- Importance-based forgetting curve

---

## Conclusion

**Phase 2 Status**: Marked "Complete" but actually ~70% complete

**Working Well**:
- Storage layer (SQLite + FTS5)
- Core memory blocks
- Basic retrieval
- Background consolidation infrastructure

**Critical Gaps**:
- Retrieval doesn't use importance/recency
- Consolidation only extracts facts
- No user profile structure
- Importance always fixed at 0.5/0.7

**Next Steps**:
1. Fix retrieval ranking (importance + temporal)
2. Add dynamic importance scoring
3. Complete episode consolidation
4. Add structured user profile

**Estimated Effort**: 3-5 days of focused work to reach "truly complete" Phase 2.
