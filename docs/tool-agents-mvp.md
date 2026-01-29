# Tool Agents MVP Implementation

Hierarchical agent delegation system allowing DialogAgent to delegate specialized tasks to lightweight sub-agents.

## What Was Built

### 1. Core Infrastructure

**ToolAgent Base Class** (`agents/tool_agent.py`)
- Stateless single-call execution
- Lazy LLM initialization
- Global context support (UserProfile)
- Natural language capability description
- Error handling with timeouts

**ToolAgentRegistry** (`core/tool_agent_registry.py`)
- Startup-initialized agent pool
- Capability summary generation for parent context
- Task delegation routing
- Agent lifecycle management

**Delegation Tool** (`tools/builtin/delegation.py`)
- Native API tool for DialogAgent
- Routes tasks to specialized agents
- Passes global context (UserProfile)
- Returns natural language results

### 2. WeatherAgent Implementation

**Location**: `agents/tool_agents/weather.py`

**Capabilities**: Weather information for any location worldwide

**Process**:
1. Extract location from natural language (LLM-based parsing)
2. Fetch weather data from wttr.in API (free, no key needed)
3. Parse JSON response (current conditions + forecast)
4. Summarize in natural language (LLM-based)

**Features**:
- Supports explicit locations ("weather in Tokyo")
- Uses user location from profile if available
- Handles errors gracefully (invalid location, API timeout)
- Returns conversational summaries (2-3 sentences)

### 3. Integration

**DialogAgent Modifications**:
- Accepts `tool_agent_registry` parameter
- Includes "Specialized Agents" section in system prompt
- Sets user profile context before processing
- Delegates via native tool calling

**Telegram Interface**:
- Initializes ToolAgentRegistry on startup
- Registers WeatherAgent with shared LLM
- Passes registry to DialogAgent

## Architecture Flow

```
User: "What's the weather in Paris?"
  ↓
DialogAgent sees in context:
  "Available specialized agents:
   - WeatherAgent: I can check current weather and forecasts..."
  ↓
DialogAgent LLM decides: "I should use WeatherAgent for this"
  ↓
DialogAgent calls tool: delegate_to_agent(agent_name="WeatherAgent", task="weather in Paris")
  ↓
ToolAgentRegistry routes to WeatherAgent
  ↓
WeatherAgent (stateless execution):
  1. Extract location: "Paris" (cheap LLM call)
  2. Fetch wttr.in API: {...json data...}
  3. Summarize: "Paris is currently 12°C with partly cloudy skies..." (cheap LLM call)
  ↓
Returns to DialogAgent: "Paris is currently 12°C..."
  ↓
DialogAgent to User: "Paris is currently 12°C with partly cloudy skies..."
```

## Token Savings

**Before** (if weather was a regular tool):
- DialogAgent context includes full weather API schema (~200 tokens)
- DialogAgent reasons about API parameters
- DialogAgent parses raw JSON results
- DialogAgent summarizes for user

**After**:
- DialogAgent context: "WeatherAgent: weather forecasts" (~10 tokens)
- DialogAgent delegates with natural language
- WeatherAgent handles all reasoning (cheap LLM)
- DialogAgent receives pre-digested summary

**Savings**: ~190 tokens per tool in DialogAgent context, specialized reasoning offloaded to cheaper models.

## Testing

Integration tests in `tests/integration/test_tool_agents.py`:
- WeatherAgent basic functionality
- ToolAgentRegistry registration and delegation
- User location context handling
- Error handling (invalid locations)

Run with: `uv run pytest tests/integration/test_tool_agents.py -v`

## Usage Example

Once deployed, users can ask:
- "What's the weather in Tokyo?"
- "Will it rain today?" (uses user's location)
- "Check weather in London"

DialogAgent automatically delegates to WeatherAgent.

## Design Decisions (MVP)

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| Lifecycle | Pool initialized on startup | Simple, no spawn overhead |
| State | Stateless, no persistence | MVP simplicity, fresh context each call |
| LLM | Lazy initialization | Save resources, connect on first use |
| Context | Global only (UserProfile) | Sufficient for MVP, extensible later |
| Error handling | Catch and return message | Safe defaults, no crashes |
| Recursion | Not implemented | Avoid complexity in MVP |
| Cost tracking | Omitted | Can add later |

## Next Steps

To add more tool agents:

1. Create new agent class inheriting `ToolAgent`
2. Implement `execute_task(task, global_context)`
3. Define `capability_description` and `agent_name`
4. Register in `telegram.py` startup

Example agents to add:
- SearchAgent (Google/Bing search)
- CalculatorAgent (math/computation)
- FileOpsAgent (file operations)
- WebFetchAgent (web scraping)
- CalendarAgent (schedule management)

## Files Modified/Created

**New Files**:
- `src/sentinel/agents/tool_agent.py`
- `src/sentinel/agents/tool_agents/__init__.py`
- `src/sentinel/agents/tool_agents/weather.py`
- `src/sentinel/core/tool_agent_registry.py`
- `src/sentinel/tools/builtin/delegation.py`
- `tests/integration/test_tool_agents.py`
- `docs/tool-agents-mvp.md` (this file)

**Modified Files**:
- `src/sentinel/agents/dialog.py` (added registry support)
- `src/sentinel/interfaces/telegram.py` (initialization)
- `src/sentinel/tools/builtin/__init__.py` (register delegation tool)

## Validation

Before testing:
1. Ensure `.env` has at least one LLM provider configured
2. Run `uv sync` to ensure dependencies are up to date
3. Weather API (wttr.in) requires no API key, works out of the box

Test sequence:
```bash
# Run integration tests
uv run pytest tests/integration/test_tool_agents.py -v

# Start Telegram bot
uv run sentinel run

# In Telegram, try:
"What's the weather in Paris?"
"Check weather in Tokyo"
"Will it rain today?"
```

DialogAgent should automatically delegate to WeatherAgent and return natural language weather summaries.
