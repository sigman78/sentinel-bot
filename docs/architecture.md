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
