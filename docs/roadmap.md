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

## Phase 5: Safety & Self-Modification
**Goal**: Safe autonomous operation

- [ ] Action classification system
- [ ] Approval workflow
- [ ] Audit logging
- [ ] Test harness for code changes
- [ ] Self-modification sandbox

Exit criteria: Agent can propose and safely apply code changes.

## Phase 6: Rich Interface
**Goal**: Full multimodal support

- [ ] Voice message handling (STT)
- [ ] Image understanding
- [ ] File processing
- [ ] Inline keyboards/actions
- [ ] Notification preferences

Exit criteria: Natural multimodal conversations.

## Future Phases

### Phase 7: Specialized Agents
- Code agent (programming tasks)
- Research agent (web search, synthesis)
- Calendar agent (scheduling)

### Phase 8: External Integrations
- Calendar APIs
- Note-taking apps
- Smart home
- Email

### Phase 9: Multi-User
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

**Phase 5: Safety & Self-Modification**

Next actions:
1. Test end-to-end with Telegram bot
2. Action classification system
3. Approval workflow for risky operations
4. Audit logging
