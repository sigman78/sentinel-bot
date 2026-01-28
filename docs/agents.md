# Agents

Agent types, lifecycle, and orchestration.

See also: [architecture.md](architecture.md), [memory.md](memory.md), [tool_calling.md](tool_calling.md)

## Agent Types

### Core Agents

#### Main Dialog Agent
Primary user-facing agent. Handles conversations, delegates specialized tasks.
- **LLM**: Claude (requires high reasoning)
- **Context**: Current conversation + relevant memories
- **Autonomy**: Can act within safe boundaries, asks for dangerous ops

#### Sleep Agent
Background memory consolidation. Runs during idle periods.
- **LLM**: Local (cost-efficient, non-urgent)
- **Tasks**:
  - Compress episodic memories into semantic facts
  - Update user profile from recent interactions
  - Prune redundant/outdated information
  - Generate memory summaries

#### Awareness Agent
Monitors context and environment. Proactive notifications.
- **LLM**: Local or OpenRouter (periodic checks)
- **Tasks**:
  - Track pending tasks and deadlines
  - Monitor external triggers (time, events)
  - Suggest proactive actions
  - Context health checks

### Specialized Agents (Future)

| Agent | Purpose | LLM Tier | Workspace |
|-------|---------|----------|-----------|
| Code | Programming tasks | Claude | Yes |
| Research | Web search, synthesis | OpenRouter | No |
| Calendar | Schedule management | Local | No |
| Writer | Long-form content | Claude | No |
| Tool | Script execution, automation | Local | Yes |

#### Code Agent
Handles programming tasks with access to Tool Workspace.
- **LLM**: Claude (complex reasoning for code)
- **Workspace access**: Full (read/write/execute)
- **Capabilities**:
  - Write Python scripts to workspace
  - Execute scripts and capture output
  - Install dependencies to isolated venv
  - Iterate on code based on errors

#### Tool Agent
Executes predefined tools and scripts.
- **LLM**: Local (structured output, tool calling)
- **Workspace access**: Execute only (predefined scripts)
- **Capabilities**:
  - Run approved scripts
  - Parse and return structured output
  - Chain tool calls for complex operations

## Agent Lifecycle

| State | Description | Transitions |
|-------|-------------|-------------|
| INIT | Loading context, memory retrieval | → READY |
| READY | Awaiting input | → ACTIVE, → TERMINATED |
| ACTIVE | Processing request | → READY, → SUSPENDED, → TERMINATED |
| SUSPENDED | Idle but preserving state | → ACTIVE (reactivate), → TERMINATED |
| TERMINATED | Resources released | (final) |

## Orchestration Rules

1. **Single active dialog**: Only one Main Dialog at a time per user
2. **Background parallelism**: Sleep/Awareness run independently
3. **Spawn limits**: Max N concurrent specialized agents
4. **Timeout**: Agents auto-terminate after inactivity
5. **Handoff**: Agents can transfer context to successor

## Agent Communication

Agents communicate via:
- **Memory Bus**: Persistent shared state
- **Message Queue**: Direct async messages (internal)
- **Orchestrator**: Coordination requests

No direct agent-to-agent calls. All coordination through Orchestrator.

## Context Management

Each agent maintains:
```python
@dataclass
class AgentContext:
    agent_id: str
    agent_type: AgentType
    conversation: list[Message]  # Current session
    memories: list[Memory]       # Retrieved relevant memories
    tools: list[Tool]            # Available capabilities
    constraints: SafetyBounds    # What this agent can do
```

Context size managed by:
- Sliding window for conversation
- Relevance-based memory retrieval
- Summarization of old context
