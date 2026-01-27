# Development Roadmap

## Phase 0: Foundation (Complete)
**Goal**: Minimal viable infrastructure

- [x] Project scaffold
- [x] Documentation structure
- [x] uv project setup
- [x] Basic package structure
- [x] Configuration management
- [x] Logging infrastructure

## Phase 1: Core Loop
**Goal**: Single agent responding via Telegram

Deliverables:
- [ ] LLM provider abstraction (Claude API)
- [ ] Basic Telegram interface
- [ ] Main dialog agent (stateless)
- [ ] Simple prompt template
- [ ] CLI interface for testing

Exit criteria: Can have basic conversation via Telegram.

## Phase 2: Memory
**Goal**: Persistent context across sessions

Deliverables:
- [ ] SQLite storage layer
- [ ] Working memory (session)
- [ ] Episodic memory (conversation logs)
- [ ] Basic retrieval (recent + keyword)
- [ ] Memory injection into prompts

Exit criteria: Bot remembers previous conversations.

## Phase 3: Multi-Provider
**Goal**: LLM flexibility and cost optimization

Deliverables:
- [ ] OpenRouter integration
- [ ] Local LLM support (Ollama/LM Studio)
- [ ] Provider router (select by task)
- [ ] Cost tracking
- [ ] Fallback logic

Exit criteria: Different queries route to appropriate LLM.

## Phase 4: Background Agents
**Goal**: Proactive behavior

Deliverables:
- [ ] Agent lifecycle management
- [ ] Sleep agent (memory consolidation)
- [ ] Awareness agent (proactive checks)
- [ ] Async task scheduler
- [ ] Semantic memory extraction

Exit criteria: Bot consolidates memories during idle, can proactively notify.

## Phase 5: Safety & Self-Modification
**Goal**: Safe autonomous operation

Deliverables:
- [ ] Action classification system
- [ ] Approval workflow
- [ ] Audit logging
- [ ] Test harness for code changes
- [ ] Self-modification sandbox

Exit criteria: Agent can propose and safely apply code changes.

## Phase 6: Rich Interface
**Goal**: Full multimodal support

Deliverables:
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

**Phase 1: Core Loop**

Next actions:
1. Implement Claude API client
2. Build basic Telegram bot
3. Create Main Dialog agent
4. Wire up CLI chat for testing
