# Project Sentinel Documentation

Personal AI agents swarm - self-evolving assistant system.

## Index

| Document | Description |
|----------|-------------|
| [architecture](architecture.md) | System design, components, data flow |
| [agents](agents.md) | Agent types, roles, orchestration |
| [memory](memory.md) | Memory hierarchy, persistence, retrieval |
| [interfaces](interfaces.md) | Human-AI communication channels |
| [safety](safety.md) | Boundaries, sandboxing, self-modification rules |
| [roadmap](roadmap.md) | Development phases, milestones |

## Package Structure

| Path | Purpose |
|------|---------|
| `src/sentinel/core/` | Orchestrator, config, shared types, logging |
| `src/sentinel/agents/` | Agent implementations (dialog, sleep, awareness) |
| `src/sentinel/memory/` | Memory hierarchy and persistence |
| `src/sentinel/interfaces/` | Telegram, CLI adapters |
| `src/sentinel/llm/` | LLM provider abstraction |
| `tests/` | Test harness |
| `data/` | SQLite DBs, file storage |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.12+, uv |
| LLM Primary | Claude API |
| LLM Fallback | OpenRouter |
| LLM Async | Local LLMs (Ollama/LM Studio) |
| Storage | SQLite + filesystem |
| Interface | Telegram Bot API |
