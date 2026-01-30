# Project Sentinel

Personal AI agents swarm - self-evolving assistant system.

![Sentinel](docs/sentinel-logo.png)

## Features

- **Multi-agent orchestration** with shared/specialized memories
- **Background agents**: sleep (memory consolidation), awareness (proactive notifications)
- **Memory hierarchy**: core memory, episodic, semantic with FTS5 full-text search
- **Intelligent LLM routing**: Claude, OpenRouter, local providers - auto-selected by task difficulty and cost
- **Task scheduling**: One-time reminders and recurring tasks with natural language parsing
- **Tool calling**: Native API integration for function execution (Anthropic/OpenAI)
- **Web search**: Real-time web search via Brave Search API
- **Sandboxed code execution**: Isolated Python workspace for agent-written scripts
- **Telegram bot** interface with persona support
- **Self-aware**: Updates human-readable agenda with notes and plans
- **Cost tracking**: Budget enforcement with automatic model downgrading

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

# Optional: External APIs
SENTINEL_BRAVE_SEARCH_API_KEY=BSA...

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
| `/memory` | Show memory system overview (hierarchy, profile, recent activity) |
| `/remind <delay> <message>` | Set one-time reminder (e.g., "5m call mom") |
| `/schedule <pattern> <message>` | Create recurring task (e.g., "daily 9am check email") |
| `/tasks` | List all scheduled tasks |
| `/cancel <task_id>` | Cancel a scheduled task |
| `/code <task>` | Generate and execute Python code |
| `/ctx` | Show debug context (raw conversation state) |

Natural language also works: "Remind me in 10 minutes to take a break"

**Note**: Commands appear in Telegram's command menu for easy access.

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
