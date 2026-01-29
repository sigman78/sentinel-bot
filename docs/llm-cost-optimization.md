# LLM Cost Optimization

Smart model selection to minimize costs while maintaining quality.

## Architecture

Different agent types use different LLM providers based on their needs:

### Premium LLM (DialogAgent)
**Priority**: Claude > OpenRouter > Local

**Used by**:
- DialogAgent (main conversation)

**Rationale**: Complex conversation, personality maintenance, tool orchestration requires best model.

### Cheap LLM (Sub-agents & Background)
**Priority**: Local > OpenRouter > Claude

**Used by**:
- WeatherAgent (stateless tool agent)
- FileAgent (agentic CLI agent)
- CodeAgent (code generation)
- SleepAgent (memory consolidation)
- AwarenessAgent (monitoring)

**Rationale**:
- Focused, well-defined tasks
- Structured input/output
- High volume operations
- Cost savings: 10-100x cheaper per token

## Cost Savings Example

**Before** (all agents use Claude Sonnet):
```
User: "What's the weather in Paris?"
→ DialogAgent (Sonnet): 2k tokens @ $3/MTok = $0.006
  ↓ delegates
→ WeatherAgent (Sonnet): 1.5k tokens @ $3/MTok = $0.0045
Total: $0.0105
```

**After** (smart routing):
```
User: "What's the weather in Paris?"
→ DialogAgent (Sonnet): 2k tokens @ $3/MTok = $0.006
  ↓ delegates
→ WeatherAgent (Local/Free): 1.5k tokens @ $0/MTok = $0.00
Total: $0.006 (43% savings)
```

Or with OpenRouter Haiku:
```
→ WeatherAgent (Haiku): 1.5k tokens @ $0.25/MTok = $0.000375
Total: $0.006375 (39% savings)
```

## Task-Based Routing

Even within a single provider, the router selects models by difficulty:

| Task Type | Difficulty | Model Selection |
|-----------|------------|-----------------|
| CHAT | 3 (Hard) | Best model (Sonnet/Opus) |
| REASONING | 3 (Hard) | Best model |
| FACT_EXTRACTION | 2 (Medium) | Mid-tier (Haiku/Sonnet) |
| SUMMARIZATION | 2 (Medium) | Mid-tier |
| TOOL_CALL | 1 (Easy) | Cheapest (Haiku/Local) |
| INTER_AGENT | 1 (Easy) | Cheapest |

## Implementation

**telegram.py startup**:
```python
# Smart LLM assignment
cheap_llm = self._get_cheap_llm()    # Local > OpenRouter > Claude
premium_llm = self._get_premium_llm()  # Claude > OpenRouter > Local

# Sub-agents get cheap models
weather_agent = WeatherAgent(llm=cheap_llm)
file_agent = AgenticCliAgent(config=..., llm=cheap_llm)
code_agent = CodeAgent(llm=cheap_llm, ...)

# DialogAgent gets premium model
dialog_agent = DialogAgent(llm=premium_llm, ...)
```

## Actual Behavior

When bot starts, you'll see:
```
INFO | Sub-agents using: local
INFO | DialogAgent using: claude
INFO | Registered WeatherAgent
INFO | Registered FileAgent
```

Or if no local model:
```
INFO | Sub-agents using: openrouter
INFO | DialogAgent using: claude
```

## Cost Tracking

With budget limits enabled:
```python
# .env
SENTINEL_DAILY_COST_LIMIT=5.0
```

Router automatically downgrades when approaching limit:
- Difficulty 3 → 2 at 80% budget
- Difficulty 2 → 1 at 90% budget

## Verification

Check actual model usage in logs:
```bash
# DialogAgent uses premium model
2026-01-29 02:00:00 | INFO | DialogAgent processing user message
2026-01-29 02:00:01 | DEBUG | Using model: claude-sonnet-4-5

# Sub-agent uses cheap model
2026-01-29 02:00:02 | INFO | WeatherAgent processing delegation
2026-01-29 02:00:02 | DEBUG | Using model: qwen2.5-coder:7b (local)
```

## Future Enhancements

1. **Per-agent budgets**: Limit spending per agent type
2. **Dynamic downgrade**: Start with cheap, upgrade only if fails
3. **Quality metrics**: Track task success rate by model
4. **Hybrid routing**: Try cheap first, retry with premium on error
