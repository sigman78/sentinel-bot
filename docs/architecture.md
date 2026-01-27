# Architecture

## Layer Overview

| Layer | Components | Responsibility |
|-------|------------|----------------|
| Interfaces | Telegram, CLI, Voice, API | Human-AI communication adapters |
| Orchestrator | Core coordinator | Message routing, agent lifecycle, safety |
| Agents | Dialog, Sleep, Awareness, Task-specific | Specialized processing units |
| Memory | Working, Episodic, Semantic, Profile, World | Persistent context and knowledge |
| LLM | Claude, OpenRouter, Local | Language model providers |

## Data Flow

1. **Inbound**: Interface → Orchestrator → Agent selection → Agent execution
2. **Memory**: Agent ↔ Memory Bus ↔ Storage
3. **LLM**: Agent → Provider Router → Best available LLM
4. **Outbound**: Agent response → Orchestrator → Interface

## Components

### Orchestrator
Central coordinator. Responsibilities:
- Message routing based on intent classification
- Agent spawn/terminate lifecycle
- Resource management (rate limits, costs)
- Safety boundary enforcement
- Background task scheduling

### Agent Runtime
Each agent:
- Has isolated context window
- Accesses shared memory via defined interfaces
- Reports actions for audit
- Can spawn sub-agents (within limits)

### Memory Bus
Unified interface for all memory operations:
- Read/write with access control
- Automatic timestamping and versioning
- Cross-agent memory sharing rules

## Concurrency Model

| Component | Model | Notes |
|-----------|-------|-------|
| Orchestrator | asyncio event loop | Single main loop |
| Agents | Parallel async tasks | Independent tasks can run parallel |
| Background agents | Periodic async tasks | Sleep, awareness run on schedule |
| LLM calls | Async with timeout | Retry and fallback logic |

## LLM Strategy

Models  selected by task 'difficulty' level (1 - Easy, 2 - Intermediate, 3 - Hard):

Some examples of difficulty assesments

| Task example | Difficulty Level | Explanation |
|--------------|------------------|-------------|
| Long term planning | 3 - Hard | Need large context with memories, complex reasoning |
| Contex rebuild | 3 - Hard | Accuracy important |
| Dialog | 3 - Hard | Maintain focus, personality, goals |
| Summarization | 2 - Intermediate | Cheaper, could run more often |
| Simple agents | 2 - Intermediate | Fast and cost optimized |
| Tool calls | 1 - Easy | build tool input, parse outputs, reason for results |
| Inter-agent | 1 - Easy | High volume, faster |

Difficulty to model mappings (sample):

| Level | Model | Rationale |
|-----------|----------|-------|-----------|
| 3 - Hard  | Claude Sonnet | Complex reasoning, reliability |
| 2 - Intermediate | Haiku or GLM | Balance |
| 1 - Easy | Qwen Instruct or similar | Fast |


### Model Selection Logic
1. Task type determines model category
2. Check model availability
3. Consider current cost budget
4. Fall back only if primary unavailable

## Tool Workspace

Sandboxed environment for code execution at `data/workspace/`.

### Structure
```
data/workspace/
├── scripts/        # Bot-written Python scripts
├── output/         # Execution output files
├── deps/           # Isolated dependencies
└── .venv/          # Workspace virtual environment
```

### Capabilities
| Operation | Allowed | Constraints |
|-----------|---------|-------------|
| Write files | Yes | Within workspace only |
| Read files | Yes | Workspace + allowed paths |
| Execute Python | Yes | Timeout, resource limits |
| Install packages | Yes | To workspace venv only |
| Network access | Limited | Whitelist only |
| System calls | No | Blocked |

### Safety Boundaries
- Scripts run in subprocess with timeout
- No access to parent directories
- No environment variable leakage
- Output captured and size-limited
- Failed scripts logged for review
