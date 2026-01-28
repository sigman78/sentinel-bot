# Development Roadmap

## Phase 0: Foundation (Complete)
**Goal**: Minimal viable infrastructure

- [x] Project scaffold
- [x] Documentation structure
- [x] uv project setup
- [x] Basic package structure
- [x] Configuration management
- [x] Logging infrastructure

## Phase 1: Core Loop (Complete)
**Goal**: Single agent responding via Telegram

- [x] LLM provider abstraction (Claude API)
- [x] Basic Telegram interface
- [x] Main dialog agent
- [x] Simple prompt template
- [x] CLI interface for testing

## Phase 2: Memory (Complete)
**Goal**: Persistent context across sessions

- [x] SQLite storage layer
- [x] Working memory (session)
- [x] Episodic memory (conversation logs)
- [x] Basic retrieval (FTS5 + fallback)
- [x] Memory injection into prompts
- [x] Core memory blocks (Letta concept)
- [x] Conversation summarization on session end
- [x] Memory importance scoring

Exit criteria: Bot remembers previous conversations.

## Phase 3: Multi-Provider (Complete)
**Goal**: LLM flexibility and cost optimization

- [x] Provider router with fallback logic
- [x] Cost tracking per request
- [x] OpenRouter integration
- [x] Local LLM support (Ollama/LM Studio)
- [x] Model selection by task type (TaskType enum)

Exit criteria: Different queries route to appropriate LLM.

## Phase 4: Background Agents (Complete)
**Goal**: Proactive behavior

- [x] Agent lifecycle management (Orchestrator)
- [x] Sleep agent (memory consolidation)
- [x] Awareness agent (proactive checks)
- [x] Async task scheduler
- [x] Semantic memory extraction

Exit criteria: Bot consolidates memories during idle, can proactively notify.

## Phase 5: Intelligent LLM Routing (Complete)
**Goal**: Cost-optimized model selection by task type

- [x] Task-based model selection (not fallback)
- [x] Model difficulty registry (HARD/INTERMEDIATE/EASY)
- [x] Task→Difficulty mapping (CHAT→HARD, SUMMARIZATION→INTERMEDIATE, etc)
- [x] Cost tracking per request with budget enforcement
- [x] Automatic downgrade when approaching budget limit
- [x] Model capability filtering (multimodal, context window)
- [x] Provider fallback and health checking
- [x] Integration tests for routing behavior

Exit criteria: Each task type routes to optimal model by cost/capability. ✅

## Phase 6: Tool Workspace (Complete)
**Goal**: Sandboxed environment for code execution

- [x] Workspace directory structure (`data/workspace/`)
- [x] Python environment isolation (venv per workspace)
- [x] Script execution with output capture (stdout/stderr)
- [x] File read/write within sandbox with path validation
- [x] Execution timeout and resource limits
- [x] Safety validator (blocks dangerous imports/functions)
- [x] CodeAgent for LLM-driven script generation
- [x] Comprehensive test coverage

Exit criteria: Bot can write, execute Python scripts and read results safely. ✅

## Phase 6.5: Task Scheduling System (Complete)
**Goal**: Proactive async task execution

- [x] Task type system (REMINDER, AGENT_TASK, API_CALL, WEB_SEARCH)
- [x] Schedule parsing (delays: "5m", "2h"; patterns: "daily 9am", "weekdays 6pm")
- [x] SQLite-backed task persistence with indexing
- [x] Recurring task rescheduling after execution
- [x] Task execution engine with notification callbacks
- [x] Telegram commands: `/remind`, `/schedule`, `/tasks`, `/cancel`
- [x] Integration with AwarenessAgent for proactive checks
- [x] Comprehensive integration test suite

Exit criteria: Users can schedule one-time and recurring tasks via natural language. ✅
Documentation: [task_system.md](task_system.md)

## Phase 6.6: Tool Calling Framework (Complete)
**Goal**: LLM-driven function execution via native APIs

- [x] Tool definition system with `@tool` decorator
- [x] Native API integration (Anthropic tool use, OpenAI function calling)
- [x] Tool registry with provider-specific converters
- [x] Built-in tools: task management, system utilities
- [x] Tool executor with validation and error handling
- [x] DialogAgent integration with two-pass approach
- [x] Automatic tool result formatting for LLM
- [x] Integration tests with live API calls

Exit criteria: Agent can call functions from natural language using native provider APIs. ✅
Documentation: [tool_calling.md](tool_calling.md)

## Phase 7: Safety & Self-Modification
**Goal**: Safe autonomous operation

- [ ] Action classification system
- [ ] Approval workflow
- [ ] Audit logging
- [ ] Test harness for code changes
- [ ] Self-modification sandbox (uses Tool Workspace)

Exit criteria: Agent can propose and safely apply code changes.

## Phase 8: Rich Interface
**Goal**: Full multimodal support

- [ ] Voice message handling (STT)
- [ ] Image understanding
- [ ] File processing
- [ ] Inline keyboards/actions
- [ ] Notification preferences

Exit criteria: Natural multimodal conversations.

## Future Phases

### Phase 9: Specialized Agents
- Code agent (uses Tool Workspace)
- Research agent (web search, synthesis)
- Calendar agent (scheduling)

### Phase 10: External Integrations
- Calendar APIs
- Note-taking apps
- Smart home
- Email

### Phase 11: Multi-User
- User isolation
- Shared knowledge base
- User-to-user introductions

---

## Development Principles

1. **Vertical slices**: Each phase delivers usable functionality
2. **Test-driven**: Tests before features
3. **Documentation-first**: Design before code
4. **Minimal dependencies**: Add only when needed
5. **Machine-readable**: Code optimized for AI understanding

## Current Focus

**Phase 7: Safety & Self-Modification** (Not Started)

Phases 0-6 complete including:
- ✅ Core infrastructure and memory
- ✅ Multi-provider LLM routing with cost optimization
- ✅ Tool Workspace for sandboxed code execution
- ✅ Task scheduling system for proactive behavior
- ✅ Native API tool calling framework

Next actions:
1. Design action classification system (read/write/execute severity levels)
2. Implement approval workflow for high-risk actions
3. Add audit logging for all agent actions
4. Create test harness for proposed code changes
5. Build self-modification sandbox using Tool Workspace
