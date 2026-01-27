# Project Sentinel

Personal AI agents swarm - self-evolving assistant system.

## Features

- Multi-agent orchestration with shared/specialized memories
- Collaborative agents: for complex tasks agents work together in hierarchical human-like org, making multiple opinions, evaluating results
- Background agents: sleep (memory consolidation), awareness (proactive notifications)
- Memory hierarchy: core memory, episodic, semantic, vector db
- LLM flexibility: Claude, OpenRouter, local providers - depending on task difficulty, agent and value
- Telegram bot interface with persona support
- Self automating: has 'isolated' workspace for agents to write and run code, interacting with host system and outside world
- Self aware: checks own performance, assistant quality, assess satisfaction, makes notes, updates human-readable agenda

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
# Clone and install
git clone <repo-url>
cd sentinel
uv sync

# Verify installation
uv run sentinel --help
```

## Configuration

Create `.env` file in project root:

```env
# Required: At least one LLM provider
SENTINEL_ANTHROPIC_API_KEY=sk-ant-...
SENTINEL_OPENROUTER_API_KEY=sk-or-...

# Required for Telegram bot
SENTINEL_TELEGRAM_TOKEN=123456:ABC...
SENTINEL_TELEGRAM_OWNER_ID=123456789

# Optional
SENTINEL_LOCAL_LLM_URL=http://localhost:1234/v1
SENTINEL_DATA_DIR=data
SENTINEL_DAILY_COST_LIMIT=5.0
```

Get Telegram bot token from [@BotFather](https://t.me/BotFather). Get your owner ID from [@userinfobot](https://t.me/userinfobot).

## Persona Files

| File | Purpose | Edited By |
|------|---------|-----------|
| `data/identity.md` | Agent personality, capabilities | User |
| `data/agenda.md` | Tasks, plans, notes | Agent |

## CLI Commands

```bash
# Initialize data directory and persona files
uv run sentinel init

# Start Telegram bot (main mode)
uv run sentinel run

# Start with debug logging (writes to data/sentinel.log)
uv run sentinel --debug run

# Interactive CLI chat (testing)
uv run sentinel chat

# Check system health
uv run sentinel health
```

## Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Initialize bot |
| `/help` | Show commands |
| `/status` | Agent status, providers, memory |
| `/clear` | Summarize and clear conversation |
| `/agenda` | Show current agenda |

## Development

```bash
# Run tests
uv run pytest -v

# Run integration tests (requires .env with API keys)
uv run pytest tests/integration -v

# Lint
uv run ruff check src tests --fix
```

## Architecture

See [docs/](docs/) for detailed documentation:
- [architecture.md](docs/architecture.md) - System design
- [agents.md](docs/agents.md) - Agent types and orchestration
- [memory.md](docs/memory.md) - Memory hierarchy
- [roadmap.md](docs/roadmap.md) - Development phases
