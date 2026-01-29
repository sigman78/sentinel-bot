# Adding New Agents

Guide for extending Sentinel with new specialized agents.

## Registration System

Sentinel uses a centralized configuration list for CLI agents. To add a new agent, create a config file and add it to the list in `configs/__init__.py`.

## Adding a CLI Agent

### 1. Create Config File

Create `src/sentinel/configs/my_agent.py`:

```python
"""My custom agent for specific tasks."""

from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits

config = AgenticCliConfig(
    name="MyAgent",
    description="I can do X, Y, and Z using specific tools",
    tools=[
        CliTool(
            name="my_tool",
            command="my_command",
            help_text="""Tool description.

Options:
  --flag    Description

Usage examples and tips...""",
            examples=[
                "my_command --flag value",
                "my_command arg1 arg2",
            ],
        ),
        # Add more tools as needed
    ],
    limits=SafetyLimits(
        timeout_seconds=60,
        max_iterations=10,
        max_consecutive_errors=2,
        max_total_errors=4,
    ),
)
```

### 2. Register Config

Add to `src/sentinel/configs/__init__.py`:

```python
from sentinel.configs.my_agent import config as my_agent_config

CLI_AGENT_CONFIGS = [
    http_agent_config,
    file_agent_config,
    my_agent_config,  # <-- Add here
]
```

### 3. Done!

The agent is now:
- Instantiated with cheap LLM on startup
- Registered in the tool agent registry
- Available to DialogAgent via `delegate_to_agent` tool

## Requirements

1. **File location**: Must be in `src/sentinel/configs/`
2. **Variable name**: Must export `config` variable
3. **Type**: `config` must be `AgenticCliConfig` instance
4. **Registration**: Add to `CLI_AGENT_CONFIGS` list in `configs/__init__.py`

## CLI Agent vs Tool Agent

### CLI Agent (AgenticCliConfig)
- Autonomous decision loop
- Self-enforced safety limits
- Executes shell commands
- Uses structured JSON output
- Auto-discovered from `configs/`

**Use when**: Building agents that need to run CLI tools autonomously

### Tool Agent (ToolAgent subclass)
- Stateless single-call execution
- Custom Python implementation
- Manually registered in `core/agent_service.py`

**Use when**: Building agents with custom logic (API wrappers, data processing, etc.)

## Example: Adding a Git Agent

```python
# src/sentinel/configs/git_agent.py
"""Git operations agent."""

from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits

config = AgenticCliConfig(
    name="GitAgent",
    description="I can perform git operations like status, log, diff, and branch management",
    tools=[
        CliTool(
            name="git",
            command="git",
            help_text="""Git version control system.

Common commands:
  status    Show working tree status
  log       Show commit logs
  diff      Show changes
  branch    List, create, or delete branches
  checkout  Switch branches
  pull      Fetch and merge from remote

Use 'git --help' for full documentation.""",
            examples=[
                "git status",
                "git log --oneline -10",
                "git diff HEAD~1",
                "git branch -a",
                "git checkout -b feature-branch",
            ],
        ),
    ],
    limits=SafetyLimits(
        timeout_seconds=30,
        max_iterations=8,
        max_consecutive_errors=2,
        max_total_errors=3,
    ),
)
```

Save and restart - GitAgent is now available!

## Testing New Agents

Create a test file:

```python
# tests/test_my_agent.py
"""Test MyAgent configuration and registration."""

from sentinel.configs.my_agent import config as my_agent_config
from sentinel.core.agent_service import discover_cli_agent_configs


def test_my_agent_config():
    """Test MyAgent config is properly defined."""
    assert my_agent_config.name == "MyAgent"
    assert "specific tasks" in my_agent_config.description
    assert len(my_agent_config.tools) > 0


def test_my_agent_in_list():
    """Test MyAgent is in CLI_AGENT_CONFIGS."""
    from sentinel.configs import CLI_AGENT_CONFIGS

    config_names = [c.name for c in CLI_AGENT_CONFIGS]
    assert "MyAgent" in config_names
```

Run: `uv run pytest tests/test_my_agent.py -v`

## Debugging Registration

Check what agents are configured:

```python
from sentinel.configs import CLI_AGENT_CONFIGS

for config in CLI_AGENT_CONFIGS:
    print(f"- {config.name}: {config.description}")
```

Check startup logs:

```
2024-01-29 10:00:00 | INFO | core.agent_service | Registered MyAgent
2024-01-29 10:00:00 | INFO | core.agent_service | Agent initialization complete. Available specialized agents: ...
```

## Adding Tool Agents (Advanced)

For custom Python logic, create a `ToolAgent` subclass:

```python
# src/sentinel/agents/tool_agents/my_tool_agent.py
"""Custom tool agent with Python logic."""

from sentinel.agents.tool_agent import ToolAgent

class MyToolAgent(ToolAgent):
    agent_name = "MyToolAgent"
    capability_description = "I can do custom Python processing"

    async def execute_task(self, task: str, global_context: dict) -> str:
        # Custom implementation
        result = await self._do_something(task)
        return result
```

Then register in `core/agent_service.py`:

```python
def initialize_agents(...):
    # ... existing code ...

    # Register custom tool agent
    my_tool_agent = MyToolAgent(llm=cheap_llm)
    registry.register(my_tool_agent)
    logger.info("Registered MyToolAgent")
```

## Best Practices

1. **Clear descriptions**: Claude uses these to choose the right agent
2. **Distinct capabilities**: Avoid overlap with existing agents
3. **Good examples**: Include diverse, realistic command examples
4. **Safety limits**: Set appropriate timeouts and iteration limits
5. **Test coverage**: Write tests for config structure and discovery
