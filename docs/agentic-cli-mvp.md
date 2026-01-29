# Agentic CLI Agent MVP

Autonomous agents that execute CLI tools in decision loops with self-enforced safety limits.

## What Was Built

### Core Infrastructure

**AgenticCliAgent** (`agents/agentic_cli.py`)
- Autonomous loop execution until task completion
- Self-enforced safety limits (timeout, iterations, errors)
- Structured JSON output for reliable parsing
- State tracking across iterations
- Natural language tool documentation

**Configuration System**
- Python-based configs (no YAML)
- CliTool with auto-help extraction
- SafetyLimits for guardrails
- Natural language documentation format

### Example Agents

**FileAgent** (`configs/file_agent.py`)
- Explore and analyze files/directories
- Tools: ls, cat, head, grep, find
- Use case: "Find all Python files and count lines"

**HttpAgent** (`configs/curl_agent.py`)
- Make HTTP requests and test APIs
- Tool: curl with auto-extracted help
- Use case: "Test if the API endpoint returns valid JSON"

## Architecture

```
User: "Find all Python files in src/"
  ↓
DialogAgent delegates to FileAgent
  ↓
AgenticCliAgent starts autonomous loop:

  Iteration 1:
    LLM: {"thinking": "Need to explore src/ first",
          "action": {"type": "call", "command": "ls -la src/"}}
    Execute: ls -la src/
    Result: sentinel/ directory found

  Iteration 2:
    LLM: {"thinking": "Check sentinel directory",
          "action": {"type": "call", "command": "find src/sentinel -name '*.py'"}}
    Execute: find...
    Result: 25 .py files found

  Iteration 3:
    LLM: {"thinking": "Task complete, found all Python files",
          "action": {"type": "done", "status": "success",
                     "result": "Found 25 Python files in src/sentinel/"}}
    → Return to DialogAgent

DialogAgent → User: "Found 25 Python files..."
```

## Self-Enforced Safety Limits

The agent enforces these limits internally in the `process()` loop:

| Limit | Default | Enforced At | Action |
|-------|---------|-------------|--------|
| Timeout | 120s | Each iteration start | Return error |
| Max iterations | 20 | Each iteration start | Return error |
| Consecutive errors | 3 | After command execution | Return error |
| Total errors | 5 | After command execution | Return error |

**Example enforcement**:
```python
# Inside AgenticCliAgent.process():
while True:
    # LIMIT 1: Timeout
    if loop_state.elapsed_seconds() >= self.limits.timeout_seconds:
        return self._create_error_response("Task timeout")

    # LIMIT 2: Max iterations
    if loop_state.current_iteration >= self.limits.max_iterations:
        return self._create_error_response("Max iterations exceeded")

    # LIMIT 3 & 4: Error counts
    if consecutive_errors >= self.limits.max_consecutive_errors:
        return self._create_error_response("Too many consecutive errors")

    # Get next action from LLM...
```

## Structured Output Format

Agent responds with JSON:

```json
{
  "thinking": "analyze current state and decide next step",
  "action": {
    "type": "call",
    "command": "full CLI command to execute"
  }
}
```

Or when complete:

```json
{
  "thinking": "successfully completed task",
  "action": {
    "type": "done",
    "status": "success",
    "result": "summary of what was accomplished"
  }
}
```

## State Tracking

Across loop iterations, agent tracks:

**AgenticLoopState**:
- Goal (original task)
- Steps completed (last 5 shown in context)
- Errors encountered (last 3 shown)
- Current iteration number
- Elapsed time

**Presented to LLM**:
```
GOAL: Find all Python files in src/
ITERATION: 2

STEPS COMPLETED:
  ✓ `ls -la src/` → sentinel/ directory found
  ✓ `find src/sentinel -name '*.py'` → 25 files found

ERRORS ENCOUNTERED: 0
```

## Configuration Example

```python
# configs/file_agent.py
from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits

config = AgenticCliConfig(
    name="FileAgent",
    description="I can explore and analyze files and directories",

    tools=[
        CliTool(
            name="ls",
            command="ls",
            help_text="List directory contents...",
            examples=["ls", "ls -la", "ls -lh /path"]
        ),
        CliTool(
            name="grep",
            command="grep",
            help_text="Search for patterns...",
            examples=["grep 'pattern' file.txt"]
        ),
    ],

    limits=SafetyLimits(
        timeout_seconds=60,
        max_iterations=15,
        max_consecutive_errors=3,
        max_total_errors=5,
    )
)
```

## Auto-Help Extraction

For standard CLI tools, auto-extract help:

```python
CliTool.from_command(
    name="curl",
    command="curl",
    auto_help=True,  # Runs `curl --help` automatically
    examples=[
        "curl https://api.github.com",
        "curl -X POST -d '{...}' https://api.example.com"
    ]
)
```

## Integration

Registered alongside stateless ToolAgents:

```python
# In telegram.py startup
from configs.file_agent import config as file_agent_config

file_agent = AgenticCliAgent(
    config=file_agent_config,
    llm=llm,
    working_dir=str(settings.data_dir.parent)
)
tool_agent_registry.register(file_agent)
```

DialogAgent sees both agent types identically:
```
Available specialized agents:
- WeatherAgent: weather forecasts worldwide (stateless)
- FileAgent: explore and analyze files (agentic loops)
```

## Test Results

All 4 integration tests passing:
- ✓ Basic file exploration (finds Python files)
- ✓ Read file contents (analyzes test file)
- ✓ Error handling (gracefully handles non-existent files)
- ✓ Safety limits (respects timeouts and iteration limits)

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Python configs | Type-safe, no YAML whitespace issues, IDE support |
| Auto-help | Leverage existing CLI documentation |
| Self-enforcement | Agent is autonomous, enforces own limits |
| Structured output | Reliable JSON parsing instead of text parsing |
| State in context | LLM sees progress, can make informed decisions |
| Full commands | LLM provides complete command string to execute |

## Comparison: Stateless vs Agentic

| Aspect | ToolAgent (Weather) | AgenticCliAgent (File) |
|--------|---------------------|----------------------|
| Execution | Single call | Loop until done |
| State | Stateless | Stateful during execution |
| Tools | One API call | Multiple CLI commands |
| Decision | Direct mapping | LLM-driven per iteration |
| Termination | Immediate | Autonomous (done/fail/limit) |
| Safety | External timeout | Self-enforced limits |

## Future Enhancements

1. **More agents**: GitAgent, DockerAgent, NpmAgent
2. **Conversation history**: Agent sees full multi-turn conversation in loop
3. **Tool learning**: Extract successful command patterns
4. **Parallel execution**: Execute independent commands concurrently
5. **Approval hooks**: Ask user before destructive commands

## Usage

Once deployed:

```
User: "Find all TODO comments in Python files"
→ FileAgent autonomously:
  1. find . -name "*.py"
  2. grep -n "TODO" *.py
  3. Returns: "Found 12 TODO comments across 5 files..."

User: "Check if the API at example.com is responding"
→ HttpAgent autonomously:
  1. curl -I https://example.com
  2. curl -s https://example.com/health
  3. Returns: "API is responding with 200 OK, health check passed"
```

## Files Created

**New Files**:
- `src/sentinel/agents/agentic_cli.py` (500+ lines)
- `configs/__init__.py`
- `configs/file_agent.py`
- `configs/curl_agent.py`
- `tests/integration/test_agentic_cli.py`
- `docs/agentic-cli-mvp.md` (this file)

**Modified Files**:
- `src/sentinel/core/tool_agent_registry.py` (support both agent types)
- `src/sentinel/interfaces/telegram.py` (register FileAgent)
