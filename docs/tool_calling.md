# Tool Calling Framework

LLM-driven function execution using native provider APIs (Anthropic tool use, OpenAI function calling).

## Overview

DialogAgent can call functions from natural language by:
1. Converting tools to provider-specific schemas
2. LLM decides which tools to use
3. Executing tools and capturing results
4. LLM formats results naturally

**Example:**
```
User: "Remind me in 5 minutes to call mom"
→ LLM calls: add_reminder(delay="5m", message="call mom")
→ Tool executes, returns task_id
→ LLM responds: "I'll remind you in 5 minutes to call mom"
```

## Architecture

```
User Input → DialogAgent → LLM (with tools) → ToolExecutor → ActionResult → LLM → Natural Response
```

### Components

**Tool Definition** (`tools/base.py`)
```python
@tool("add_reminder", "Set a one-time reminder")
async def add_reminder(delay: str, message: str) -> ActionResult:
    manager = _get_task_manager()
    return await manager.add_reminder(delay, message)
```

**Tool Registry** (`tools/registry.py`)
- Central registry for all tools
- `to_anthropic_tools()` - Anthropic format
- `to_openai_tools()` - OpenAI format
- Context string generation (legacy)

**Tool Executor** (`tools/executor.py`)
- Validates arguments
- Executes tool functions
- Handles errors gracefully
- Formats results for LLM

**DialogAgent Integration** (`agents/dialog.py`)
- Detects provider type and converts tools
- Two-pass approach:
  1. First call: LLM with tools → tool calls
  2. Execute tools → results
  3. Second call: LLM with results → natural response
- Simplified message flow (no empty assistant messages)

## Native API Integration

**Anthropic (Claude)**
```python
# Convert tools to Anthropic format
tools = registry.to_anthropic_tools()

# Send to API
response = await client.messages.create(
    model="claude-3-5-sonnet-20241022",
    tools=tools,  # Native tool definitions
    messages=[...]
)

# Extract tool_use blocks
for block in response.content:
    if block.type == "tool_use":
        tool_calls.append({
            "id": block.id,
            "name": block.name,
            "input": block.input
        })
```

**OpenAI / OpenRouter / Local**
```python
# Convert tools to OpenAI format
tools = registry.to_openai_tools()

# Send to API
response = await client.chat.completions.create(
    model="gpt-4",
    tools=tools,  # Native function definitions
    messages=[...]
)

# Extract tool_calls
if response.choices[0].message.tool_calls:
    for tc in response.choices[0].message.tool_calls:
        tool_calls.append({
            "id": tc.id,
            "name": tc.function.name,
            "input": json.loads(tc.function.arguments)
        })
```

## Built-in Tools

**Task Management** (`tools/builtin/tasks.py`)
- `add_reminder(delay, message)` - One-time reminder
- `add_recurring_task(schedule, task_type, description, data)` - Recurring task
- `list_tasks()` - List active tasks
- `cancel_task(task_id)` - Cancel task

**System Utilities** (`tools/builtin/system.py`)
- `get_current_time()` - Current date/time with formatting

## Key Features

- ✅ Native API integration (no JSON parsing)
- ✅ Provider-specific format conversion
- ✅ Automatic result formatting with datetime handling
- ✅ Error handling and validation
- ✅ Integration tests with live APIs
- ✅ Two-pass approach for natural responses

## Usage

**Automatic (Natural Language):**
```
User: "What time is it?"
→ get_current_time() called automatically
→ LLM: "It's currently 2:30 PM on Monday, January 27th."
```

**Tool Definition:**
```python
from sentinel.tools.base import tool
from sentinel.core.types import ActionResult

@tool(
    "my_tool",
    "Description of what the tool does",
    requires_approval=False,
    risk_level=RiskLevel.LOW
)
async def my_tool(param1: str, param2: int) -> ActionResult:
    # Tool implementation
    return ActionResult(
        success=True,
        data={"result": "value"}
    )
```

**Registration:**
```python
from sentinel.tools.registry import get_global_registry

registry = get_global_registry()
registry.register(my_tool._tool)
```

## Implementation Notes

- Tools passed via native `tools` parameter (not system prompt)
- LLMRouter forwards tools to providers
- ToolParser kept for legacy/fallback but unused
- JSON serialization uses DateTimeEncoder for datetime objects
- Empty responses trigger fallback formatting

## Testing

Integration tests verify:
- Natural language → tool call conversion
- Tool execution with results
- Recurring task creation
- Task listing
- Direct tool execution (unit-style)

See `tests/integration/test_tool_calling.py` for details.

## Format Specifications

**Anthropic Tool Format:**
```json
{
  "name": "tool_name",
  "description": "What the tool does",
  "input_schema": {
    "type": "object",
    "properties": {
      "param": {"type": "string", "description": "..."}
    },
    "required": ["param"]
  }
}
```

**OpenAI Function Format:**
```json
{
  "type": "function",
  "function": {
    "name": "tool_name",
    "description": "What the tool does",
    "parameters": {
      "type": "object",
      "properties": {
        "param": {"type": "string", "description": "..."}
      },
      "required": ["param"]
    }
  }
}
```
