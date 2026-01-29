# Agent Architecture Memo

Current agent implementation analysis (codebase review).

## Agent Types

### 1. DialogAgent (Main)
**Purpose**: Primary user-facing conversational agent

**Inputs**:
- User messages (Message objects) from Telegram interface
- Identity persona (identity.md file)
- Current agenda (agenda.md file)
- User profile (structured from memory store)
- Relevant memories (episodic/semantic via FTS5 search)

**Outputs**:
- Assistant messages (Message objects) back to user
- Updated agenda sections (writes to agenda.md)
- Episodic memories (conversation exchanges with importance scores)
- User profile updates (preferences, context, metadata)

**Communication**:
- Read: identity.md, agenda.md, user profile, memory store
- Write: agenda.md, episodic memories, user profile
- Uses: LLM router (task-based model selection), ToolRegistry, ToolExecutor
- Tools: Native API tool calling (Anthropic/OpenAI formats)

**Key Features**:
- Sliding window conversation history (max 20 messages)
- Dynamic importance scoring for memory persistence
- Tool execution with two-pass LLM (call tools, then natural response)
- Session summarization with LLM-based importance rating

---

### 2. SleepAgent (Background)
**Purpose**: Memory consolidation during idle periods

**Inputs**: None (autonomous execution via orchestrator)

**Outputs**: Statistics dict (facts_extracted, memories_consolidated, memories_decayed)

**Communication**:
- Read: Recent episodic memories from store (limit 20)
- Write: Semantic facts, consolidated episodic memories
- Uses: LLM for fact extraction and summarization

**Process**:
1. Extract durable facts from episodic summaries → semantic memory
2. Group similar memories (50%+ keyword overlap, within 7 days)
3. Consolidate groups into single summary, mark originals low importance
4. Apply importance decay to old memories (planned, not yet implemented)

**Trigger**: Scheduled hourly by orchestrator (LOW priority, 10min initial delay)

---

### 3. AwarenessAgent (Background)
**Purpose**: Proactive monitoring and time-based notifications

**Inputs**:
- Programmatic: add_reminder(), add_monitor()
- Natural language: parse "remind me" messages (planned, not fully implemented)

**Outputs**: Notification strings (via callback or queued)

**Communication**:
- Internal state: Reminder and Monitor objects (in-memory, not persistent)
- Calls: notify_callback (async) to send notifications to user
- No LLM usage in current implementation

**Features**:
- One-time and recurring reminders (with trigger_at, recurring timedelta)
- Conditional monitors (custom check functions, configurable intervals)
- Notification queue for when callback unavailable

**Trigger**: Scheduled every 1 minute by orchestrator (NORMAL priority)

---

### 4. CodeAgent (Specialized)
**Purpose**: Sandboxed Python script execution for user tasks

**Inputs**: User messages with code task description (via /code command)

**Outputs**: Execution results, LLM-analyzed summary, script path

**Communication**:
- Read: User task description
- Write: Python scripts to workspace, execution results to episodic memory
- Uses: LLM for script generation and output analysis, WorkspaceManager, ScriptExecutor

**Process**:
1. Generate Python script from task description (LLM, low temp 0.2)
2. Save script to isolated workspace (task_{msg_id}_{uuid}.py)
3. Execute in sandbox (subprocess with timeout, resource limits)
4. Analyze results with LLM (exit code, stdout, stderr → summary)
5. Persist execution metadata to episodic memory (importance 0.6)

**Trigger**: Explicitly invoked via /code command (not background)

---

## Orchestrator

**Purpose**: Agent lifecycle and background task scheduling

**Not an agent** - coordination layer that manages:
- Agent registry (by agent_id)
- ScheduledTask queue (with priorities: LOW, NORMAL, HIGH)
- Idle detection (5min threshold for triggering background work)
- Scheduler loop (1sec tick, executes pending tasks by priority)

**Scheduled Tasks**:
- `sleep_consolidation`: Every 1 hour → SleepAgent.run_consolidation()
- `awareness_check`: Every 1 minute → AwarenessAgent.check_all()
- User tasks via TaskManager: One-time and recurring (natural language parsed)

**Key Rule**: No direct agent-to-agent communication. All coordination via orchestrator or shared MemoryStore.

---

## Communication Patterns

```
User Input (Telegram)
  ↓
DialogAgent (processes message)
  ↓ reads
  ├── identity.md (persona)
  ├── agenda.md (current tasks/notes)
  ├── UserProfile (preferences, context)
  └── MemoryStore (episodic, semantic, FTS5 search)
  ↓ uses
  ├── LLM Router (task-based model selection)
  ├── ToolRegistry (available tools metadata)
  └── ToolExecutor (executes tool calls)
  ↓ writes
  ├── agenda.md (agent's notes/plans)
  ├── MemoryStore (episodic memories)
  └── UserProfile (learned preferences)
  ↓
User Response (Telegram)

Background Loop (Orchestrator):
  Every 1 hour → SleepAgent
    ↓ reads
    └── MemoryStore (episodic)
    ↓ writes
    └── MemoryStore (semantic facts, consolidated)

  Every 1 minute → AwarenessAgent
    ↓ checks
    ├── Reminders (time-based)
    └── Monitors (condition-based)
    ↓ sends
    └── Notifications (via callback)
```

---

## Data Flow Summary

| Agent | Reads From | Writes To | Triggered By |
|-------|-----------|-----------|--------------|
| DialogAgent | identity.md, agenda.md, UserProfile, MemoryStore | agenda.md, MemoryStore, UserProfile | User message |
| SleepAgent | MemoryStore (episodic) | MemoryStore (semantic, consolidated) | Orchestrator (hourly) |
| AwarenessAgent | Internal state (reminders, monitors) | Notifications (callback) | Orchestrator (1min) |
| CodeAgent | User task | Workspace scripts, MemoryStore | /code command |

---

## Agent States

All agents inherit state machine from BaseAgent:
- **INIT**: Loading context, memory retrieval
- **READY**: Awaiting input
- **ACTIVE**: Processing request
- **SUSPENDED**: Idle but preserving state (not currently used)
- **TERMINATED**: Resources released

---

## Notes

- **No multi-agent collaboration**: Agents don't spawn or delegate to each other directly
- **Shared memory only**: Communication via persistent MemoryStore (SQLite + FTS5)
- **No agent message queue**: Background agents scheduled, not event-driven
- **DialogAgent is singleton**: Only one active dialog per user at a time
- **Tool calling**: Native API support (Anthropic/OpenAI formats), not text parsing
- **Importance scoring**: Used for memory retrieval prioritization and consolidation
