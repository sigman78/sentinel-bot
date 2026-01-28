# Tool Calling Framework Design

## Overview

Implement LLM-driven function execution where the language model decides when to use tools based on natural language input, outputs structured JSON, and receives execution results.

## Architecture

### Flow
```
User: "Remind me in 5 minutes to call mom"
    ↓
DialogAgent (tool-aware)
    ↓
LLM with tool definitions in system prompt
    ↓
Output: {"tool": "add_reminder", "args": {"delay": "5m", "message": "call mom"}}
    ↓
ToolParser extracts JSON from response
    ↓
ToolExecutor validates and executes
    ↓
Result: {"success": true, "reminder_id": "abc123", "trigger_at": "2026-01-27T14:35:00"}
    ↓
Feed result back to LLM as system message
    ↓
LLM: "I'll remind you at 14:35 to call mom."
```

## Components

### 1. Tool Definition (`tools/base.py`)

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema format
    executor: Callable[[dict], Awaitable[ActionResult]]
    requires_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW

# Decorator for easy tool registration
def tool(name: str, description: str, **schema_kwargs):
    def decorator(func):
        # Auto-generate JSON schema from function signature
        # Register with ToolRegistry
        return func
    return decorator
```

### 2. Tool Registry (`tools/registry.py`)

Central registry that:
- Discovers tools via decorators
- Provides tool definitions for LLM context
- Validates tool names and parameters
- Routes execution to correct executor

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None
    def get(self, name: str) -> Tool | None
    def get_all(self) -> list[Tool]
    def get_context_string(self) -> str  # For LLM system prompt
```

### 3. Tool Executor (`tools/executor.py`)

Parses LLM output and executes tools:

```python
class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    async def execute_from_text(self, llm_response: str) -> list[ActionResult]:
        """Parse JSON tool calls and execute them."""
        tool_calls = ToolParser.extract_calls(llm_response)
        results = []
        for call in tool_calls:
            tool = self.registry.get(call.tool_name)
            if tool.requires_approval:
                # Queue for approval workflow
                pass
            result = await tool.executor(call.arguments)
            results.append(result)
        return results
```

### 4. Tool Parser (`tools/parser.py`)

Extracts tool calls from LLM text:

```python
@dataclass
class ToolCall:
    tool_name: str
    arguments: dict[str, Any]
    raw_json: str

class ToolParser:
    @staticmethod
    def extract_calls(text: str) -> list[ToolCall]:
        """Extract JSON tool calls from LLM response."""
        # Look for ```json blocks or raw JSON objects
        # Validate against schema
        pass
```

### 5. Built-in Tools

#### Task Management Tools (`tools/builtin/tasks.py`)

```python
@tool("add_reminder", "Set a one-time reminder", delay=str, message=str)
async def add_reminder(delay: str, message: str) -> ActionResult:
    """Parse delay like '5m', '2h', '1d' and schedule reminder."""
    pass

@tool("add_recurring_task", "Schedule recurring task",
      schedule=str, task_type=str, description=str, execution_data=dict)
async def add_recurring_task(schedule: str, task_type: str,
                            description: str, execution_data: dict) -> ActionResult:
    """
    Schedule recurring task.

    schedule: "daily 9am", "weekdays 6pm", "monday 10am", "*/15 * * * *" (cron)
    task_type: "reminder", "agent_task", "api_call", "web_search"
    execution_data: Task-specific data
    """
    pass

@tool("list_tasks", "List active scheduled tasks")
async def list_tasks() -> ActionResult:
    pass

@tool("cancel_task", "Cancel a scheduled task", task_id=str)
async def cancel_task(task_id: str) -> ActionResult:
    pass
```

#### Memory Tools (`tools/builtin/memory.py`)

```python
@tool("search_memory", "Search past conversations and facts", query=str)
async def search_memory(query: str, limit: int = 5) -> ActionResult:
    pass

@tool("save_note", "Save important information to memory", content=str, tags=list)
async def save_note(content: str, tags: list[str] | None = None) -> ActionResult:
    pass
```

#### Web Tools (`tools/builtin/web.py`)

```python
@tool("search_web", "Search the web", query=str)
async def search_web(query: str) -> ActionResult:
    """Use SerpAPI or similar."""
    pass

@tool("fetch_url", "Fetch content from URL", url=str)
async def fetch_url(url: str) -> ActionResult:
    pass

@tool("api_call", "Make HTTP API request",
      url=str, method=str, headers=dict, body=dict)
async def api_call(url: str, method: str = "GET",
                  headers: dict | None = None,
                  body: dict | None = None) -> ActionResult:
    """Generic HTTP client for user-defined API calls."""
    pass
```

#### System Tools (`tools/builtin/system.py`)

```python
@tool("execute_code", "Execute Python code in sandbox", code=str)
async def execute_code(code: str) -> ActionResult:
    """Delegates to CodeAgent."""
    pass

@tool("get_current_time", "Get current date and time")
async def get_current_time() -> ActionResult:
    pass
```

## Task Management System

### Database Schema (`memory/store.py` additions)

```sql
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,  -- 'reminder', 'agent_task', 'api_call', 'web_search'
    description TEXT NOT NULL,
    schedule_type TEXT NOT NULL,  -- 'once', 'recurring'
    schedule_data TEXT NOT NULL,  -- JSON: {"delay": "5m"} or {"cron": "0 9 * * *"}
    execution_data TEXT,  -- JSON with task-specific params
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_run DATETIME,
    next_run DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_next_run
    ON scheduled_tasks(next_run) WHERE enabled = 1;
```

### Task Types (`tasks/types.py`)

```python
class TaskType(Enum):
    REMINDER = "reminder"           # Simple notification
    AGENT_TASK = "agent_task"       # Delegate to agent, send result
    API_CALL = "api_call"           # HTTP request
    WEB_SEARCH = "web_search"       # Search + summarize

@dataclass
class ScheduledTask:
    id: str
    task_type: TaskType
    description: str
    schedule_type: str  # 'once' | 'recurring'
    schedule_data: dict  # {"delay": "5m"} | {"cron": "0 9 * * *"}
    execution_data: dict | None
    enabled: bool
    created_at: datetime
    last_run: datetime | None
    next_run: datetime
```

### Task Executor (`tasks/executor.py`)

```python
class TaskExecutor:
    """Executes different task types."""

    async def execute(self, task: ScheduledTask) -> ActionResult:
        if task.task_type == TaskType.REMINDER:
            return await self._execute_reminder(task)
        elif task.task_type == TaskType.AGENT_TASK:
            return await self._execute_agent_task(task)
        elif task.task_type == TaskType.API_CALL:
            return await self._execute_api_call(task)
        elif task.task_type == TaskType.WEB_SEARCH:
            return await self._execute_web_search(task)

    async def _execute_reminder(self, task: ScheduledTask) -> ActionResult:
        """Send notification."""
        pass

    async def _execute_agent_task(self, task: ScheduledTask) -> ActionResult:
        """
        Delegate to DialogAgent/CodeAgent.
        execution_data: {"prompt": "Search top 3 US news and summarize"}
        """
        pass

    async def _execute_api_call(self, task: ScheduledTask) -> ActionResult:
        """
        Make HTTP request.
        execution_data: {"url": "http://home.lan/lights/off", "method": "POST"}
        """
        pass

    async def _execute_web_search(self, task: ScheduledTask) -> ActionResult:
        """
        Search and summarize.
        execution_data: {"query": "US top news", "limit": 3}
        """
        pass
```

### Schedule Parser (`tasks/parser.py`)

```python
class ScheduleParser:
    @staticmethod
    def parse_delay(text: str) -> timedelta:
        """
        Parse: "5m", "2h", "1d", "30s"
        Returns: timedelta
        """
        pass

    @staticmethod
    def parse_recurring(text: str) -> dict:
        """
        Parse: "daily 9am", "weekdays 6pm", "monday 10am", "*/15 * * * *"
        Returns: {"cron": "0 9 * * *"} or {"pattern": "daily", "time": "09:00"}
        """
        pass

    @staticmethod
    def calculate_next_run(schedule_data: dict, after: datetime) -> datetime:
        """Calculate next run time from cron or pattern."""
        pass
```

## Integration with DialogAgent

### Modified Dialog Agent

```python
class DialogAgent(BaseAgent):
    def __init__(self, llm: LLMProvider, memory: MemoryStore,
                 tool_registry: ToolRegistry | None = None):
        self.tool_registry = tool_registry or get_default_registry()
        self.tool_executor = ToolExecutor(self.tool_registry)
        # ... existing init

    async def process(self, message: Message) -> Message:
        # Add tool definitions to system prompt
        system_prompt = self._build_system_prompt_with_tools()

        # Get LLM response
        llm_response = await self.llm.complete(messages, system_prompt)

        # Check for tool calls
        tool_calls = ToolParser.extract_calls(llm_response)

        if tool_calls:
            # Execute tools
            results = await self.tool_executor.execute_all(tool_calls)

            # Feed results back to LLM for natural language response
            result_message = self._format_tool_results(results)
            messages.append({"role": "system", "content": result_message})

            final_response = await self.llm.complete(messages, system_prompt)
            return Message(..., content=final_response)
        else:
            # No tool calls, direct response
            return Message(..., content=llm_response)

    def _build_system_prompt_with_tools(self) -> str:
        """Add tool definitions to system prompt."""
        base_prompt = self.config.system_prompt
        tool_context = self.tool_registry.get_context_string()

        return f"""
{base_prompt}

# AVAILABLE TOOLS

You have access to the following tools to help complete tasks:

{tool_context}

When you need to use a tool, output a JSON block like this:

```json
{{
    "tool": "tool_name",
    "args": {{
        "param1": "value1",
        "param2": "value2"
    }}
}}
```

You can call multiple tools by outputting multiple JSON blocks.
After tool execution, you'll receive the results and can respond naturally.
"""
```

## System Prompt Extension

```
# AVAILABLE TOOLS

add_reminder(delay: str, message: str)
  Set a one-time reminder.
  delay: Time delay like "5m", "2h", "1d"
  message: Reminder text

add_recurring_task(schedule: str, task_type: str, description: str, execution_data: dict)
  Schedule a recurring task.
  schedule: "daily 9am", "weekdays 6pm", "*/15 * * * *" (cron)
  task_type: "reminder" | "agent_task" | "api_call" | "web_search"
  execution_data: Task-specific parameters

list_tasks()
  List all active scheduled tasks.

cancel_task(task_id: str)
  Cancel a scheduled task.

search_memory(query: str, limit: int = 5)
  Search past conversations and saved facts.

execute_code(code: str)
  Execute Python code in a secure sandbox.

get_current_time()
  Get current date and time.

# TOOL USAGE

When you need to use a tool, output:

```json
{
    "tool": "tool_name",
    "args": {
        "param": "value"
    }
}
```

Examples:

User: "Remind me in 10 minutes to check the oven"
Assistant: ```json
{
    "tool": "add_reminder",
    "args": {
        "delay": "10m",
        "message": "check the oven"
    }
}
```

User: "Search web for top US news every weekday at 9am and tell me the top 3"
Assistant: ```json
{
    "tool": "add_recurring_task",
    "args": {
        "schedule": "weekdays 9am",
        "task_type": "web_search",
        "description": "Search top US news and summarize top 3",
        "execution_data": {
            "query": "US top news",
            "limit": 3,
            "summarize": true
        }
    }
}
```

User: "Turn off the lights at 1am daily"
Assistant: ```json
{
    "tool": "add_recurring_task",
    "args": {
        "schedule": "daily 1am",
        "task_type": "api_call",
        "description": "Turn off home lights",
        "execution_data": {
            "url": "http://home.lan/lights/off",
            "method": "POST"
        }
    }
}
```
```

## Implementation Order

### Phase 1: Core Tool Framework
1. `tools/base.py` - Tool dataclass, decorators
2. `tools/registry.py` - ToolRegistry
3. `tools/parser.py` - Extract JSON from LLM text
4. `tools/executor.py` - Execute tools, return results
5. Test with simple mock tool

### Phase 2: Task Management
1. `tasks/types.py` - TaskType, ScheduledTask
2. `tasks/parser.py` - Parse delays and cron schedules
3. `memory/store.py` - Add scheduled_tasks table and CRUD
4. `tasks/store.py` - TaskStore wrapper
5. `tasks/executor.py` - Execute different task types
6. `tasks/manager.py` - TaskManager orchestration

### Phase 3: Built-in Tools
1. `tools/builtin/tasks.py` - Task management tools
2. `tools/builtin/system.py` - Time, code execution
3. `tools/builtin/memory.py` - Memory search/save
4. `tools/builtin/web.py` - Web search, API calls (if providers available)

### Phase 4: Integration
1. Modify `agents/dialog.py` - Add tool awareness
2. Modify `interfaces/telegram.py` - Wire TaskManager, add commands
3. Modify `agents/awareness.py` - Check persistent tasks from DB
4. Add integration tests

## Testing Strategy

### Unit Tests
- Tool registration and discovery
- JSON parsing from various LLM outputs
- Schedule parsing ("5m", "daily 9am", cron)
- Task execution for each type
- Tool argument validation

### Integration Tests
- End-to-end: user message → tool call → execution → LLM response
- Task scheduling and execution
- Recurring task reschedule logic
- Error handling and fallbacks

## Future Enhancements

1. **Tool Composition**: Chain multiple tools in sequence
2. **Approval Workflow**: Queue dangerous actions for user confirmation
3. **Tool Results History**: Store tool execution history in memory
4. **Dynamic Tool Loading**: Load tools from `data/custom_tools/`
5. **Tool Analytics**: Track which tools are used most
6. **Multi-step Planning**: Let LLM plan multi-tool sequences
7. **Tool Suggestions**: Proactively suggest relevant tools
