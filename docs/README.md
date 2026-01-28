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
| [task_system_implementation](task_system_implementation.md) | Task scheduling design and implementation |
| [task_system_testing](task_system_testing.md) | Task system test report |
| [tool_calling_design](tool_calling_design.md) | Tool calling framework design |
| [tool_calling_implementation](tool_calling_implementation.md) | Tool calling implementation details |

## Package Structure

| Path | Purpose |
|------|---------|
| `src/sentinel/core/` | Orchestrator, config, shared types, logging |
| `src/sentinel/agents/` | Agent implementations (dialog, sleep, awareness, code) |
| `src/sentinel/memory/` | Memory hierarchy and persistence |
| `src/sentinel/interfaces/` | Telegram, CLI adapters |
| `src/sentinel/llm/` | LLM provider abstraction and intelligent routing |
| `src/sentinel/tasks/` | Task scheduling, parsing, execution |
| `src/sentinel/tools/` | Tool calling framework, registry, built-in tools |
| `src/sentinel/workspace/` | Sandboxed code execution environment |
| `tests/` | Unit tests |
| `tests/integration/` | Integration tests with live APIs |
| `data/` | SQLite DBs, workspace, file storage |

## Tech Stack

| Component | Technology |
|-----------|------------|
| Runtime | Python 3.12+, uv |
| LLM Providers | Anthropic (Claude), OpenRouter, Local (Ollama/LM Studio) |
| Tool Calling | Native Anthropic tool use, OpenAI function calling |
| Storage | SQLite (aiosqlite) with FTS5 full-text search |
| Task Scheduling | SQLite-backed with async execution |
| Code Execution | Isolated Python venvs with sandbox validation |
| Interface | Telegram Bot API, CLI |
| Testing | pytest with integration tests |

## Agent Persona Files

| File | Purpose | Edited By |
|------|---------|-----------|
| `data/identity.md` | Agent personality, capabilities, working style | User |
| `data/agenda.md` | Ongoing tasks, plans, preferences, notes | Agent (self-edited) |

These files are loaded at agent initialization and used to build the system prompt context.
