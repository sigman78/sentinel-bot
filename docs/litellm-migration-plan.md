# LiteLLM Migration Plan

Refactor Sentinel's LLM layer to use LiteLLM SDK while preserving our semantic task-aware routing.

## Strategy: Hybrid Approach

**Use LiteLLM for**: Provider abstraction, API translation, maintained pricing database, broader model support
**Keep our custom**: Task-aware routing logic, difficulty-based model selection, budget auto-downgrade, simple cost tracking

## Current Architecture

```
┌─────────────┐
│   Agents    │
└──────┬──────┘
       │
       v
┌─────────────────┐      ┌──────────────┐
│   LLMRouter     │─────>│ CostTracker  │
└────────┬────────┘      └──────────────┘
         │
    ┌────┴────┬────────┬─────────┐
    v         v        v         v
┌────────┐ ┌────┐ ┌──────────┐ ┌──────┐
│ Claude │ │ OR │ │ Local    │ │ Base │
│Provider│ │Prov│ │ Provider │ │ LLM  │
└────────┘ └────┘ └──────────┘ └──────┘
    │         │         │
    v         v         v
 Anthropic  OpenRouter  Ollama
   API        API        API
```

## Target Architecture

```
┌─────────────┐
│   Agents    │
└──────┬──────┘
       │
       v
┌─────────────────────┐      ┌──────────────┐
│ SentinelLLMRouter   │─────>│ CostTracker  │
│ (task-aware logic)  │      └──────────────┘
└──────────┬──────────┘
           │
           v
┌──────────────────────┐      ┌────────────────┐
│   LiteLLMAdapter     │─────>│ ModelRegistry  │
│ (unified interface)  │      │ (YAML config)  │
└──────────┬───────────┘      └────────────────┘
           │
           v
    ┌──────────────┐
    │   LiteLLM    │
    │  completion()│
    └──────┬───────┘
           │
      ┌────┴────┬────────┬─────────┐
      v         v        v         v
  Anthropic  OpenRouter Ollama   100+
    API        API       API    others
```

## What Changes

### Files to Replace/Modify

| File | Action | Reason |
|------|--------|--------|
| `llm/claude.py` | **DELETE** | Replaced by LiteLLM |
| `llm/openrouter.py` | **DELETE** | Replaced by LiteLLM |
| `llm/local.py` | **DELETE** | Replaced by LiteLLM |
| `llm/base.py` | **MODIFY** | Simplify, keep `LLMResponse` and `LLMConfig` |
| `llm/router.py` | **REFACTOR** | Keep task logic, use LiteLLM adapter |
| `llm/registry.py` | **REPLACE** | Move to YAML config file |
| `llm/cost_tracker.py` | **SIMPLIFY** | Use LiteLLM's cost data, keep budget logic |

### Files to Keep

| File | Keep | Reason |
|------|------|--------|
| `llm/router.py` | ✅ | Task-aware routing is our core value |
| `llm/cost_tracker.py` | ✅ | Budget auto-downgrade logic |
| `agents/*.py` | ✅ | No changes needed |
| `tests/` | ✅ | Update to test new implementation |

## Migration Steps

### Phase 1: Setup & Configuration

**1.1 Install LiteLLM**
```bash
uv add litellm
```

**1.2 Create Model Registry Config**

Create `src/sentinel/configs/models.yaml`:

```yaml
# Model registry for Sentinel
# Maps task difficulty to available models with cost/capability metadata

models:
  # Hard difficulty (3) - Complex reasoning
  - model_id: claude-sonnet-4-20250514
    litellm_name: anthropic/claude-sonnet-4-20250514
    provider: anthropic
    difficulty: 3
    cost_per_1m_input: 3.0
    cost_per_1m_output: 15.0
    max_context: 200000
    avg_latency_ms: 2000
    quality_score: 0.95
    multimodal: true
    supports_tools: true
    notes: "Balanced quality/cost for complex tasks"
    auth_env: SENTINEL_ANTHROPIC_API_KEY

  - model_id: claude-opus-4-20250514
    litellm_name: anthropic/claude-opus-4-20250514
    provider: anthropic
    difficulty: 3
    cost_per_1m_input: 15.0
    cost_per_1m_output: 75.0
    max_context: 200000
    avg_latency_ms: 3000
    quality_score: 1.0
    multimodal: true
    supports_tools: true
    notes: "Best reasoning, highest cost"
    auth_env: SENTINEL_ANTHROPIC_API_KEY

  # Intermediate difficulty (2)
  - model_id: claude-haiku-3-5
    litellm_name: anthropic/claude-haiku-3-5-20241022
    provider: anthropic
    difficulty: 2
    cost_per_1m_input: 0.8
    cost_per_1m_output: 4.0
    max_context: 200000
    avg_latency_ms: 800
    quality_score: 0.85
    multimodal: true
    supports_tools: true
    notes: "Fast, cheap, good for simple tasks"
    auth_env: SENTINEL_ANTHROPIC_API_KEY

  - model_id: gemini-pro-1.5
    litellm_name: gemini/gemini-1.5-pro
    provider: vertex_ai
    difficulty: 2
    cost_per_1m_input: 1.25
    cost_per_1m_output: 5.0
    max_context: 1000000
    avg_latency_ms: 2000
    quality_score: 0.85
    multimodal: true
    supports_tools: true
    notes: "Huge context window"
    auth_env: SENTINEL_OPENROUTER_API_KEY

  # Easy difficulty (1)
  - model_id: gpt-4o-mini
    litellm_name: openai/gpt-4o-mini
    provider: openai
    difficulty: 1
    cost_per_1m_input: 0.15
    cost_per_1m_output: 0.6
    max_context: 128000
    avg_latency_ms: 1000
    quality_score: 0.75
    multimodal: true
    supports_tools: true
    auth_env: SENTINEL_OPENROUTER_API_KEY

  - model_id: gemini-flash-1.5
    litellm_name: gemini/gemini-1.5-flash
    provider: vertex_ai
    difficulty: 1
    cost_per_1m_input: 0.075
    cost_per_1m_output: 0.3
    max_context: 1000000
    avg_latency_ms: 800
    quality_score: 0.7
    multimodal: true
    supports_tools: true
    notes: "Very fast, huge context"
    auth_env: SENTINEL_OPENROUTER_API_KEY

  - model_id: llama-3.1-8b
    litellm_name: ollama/llama3.1:8b
    provider: ollama
    difficulty: 1
    cost_per_1m_input: 0.0
    cost_per_1m_output: 0.0
    max_context: 128000
    avg_latency_ms: 600
    quality_score: 0.65
    supports_tools: true
    notes: "Free local inference"
    auth_env: null
    base_url_env: SENTINEL_LOCAL_LLM_URL

# Routing preferences
routing:
  # Budget threshold for auto-downgrade (0.0-1.0)
  budget_threshold: 0.8

  # Default task difficulty mapping
  task_difficulty:
    chat: 3
    reasoning: 3
    fact_extraction: 2
    summarization: 2
    background: 2
    simple: 1
    tool_call: 1
    inter_agent: 1
    importance_scoring: 1
```

### Phase 2: Core Implementation

**2.1 Create LiteLLM Adapter** (`llm/litellm_adapter.py`)

```python
"""LiteLLM adapter - unified interface for all LLM providers."""

import os
from pathlib import Path
from typing import Any

import litellm
import yaml
from litellm import acompletion

from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMResponse

logger = get_logger("llm.litellm_adapter")


class ModelConfig:
    """Model configuration from YAML."""

    def __init__(self, data: dict[str, Any]):
        self.model_id = data["model_id"]
        self.litellm_name = data["litellm_name"]
        self.provider = data["provider"]
        self.difficulty = data["difficulty"]
        self.cost_per_1m_input = data["cost_per_1m_input"]
        self.cost_per_1m_output = data["cost_per_1m_output"]
        self.max_context = data["max_context"]
        self.avg_latency_ms = data["avg_latency_ms"]
        self.quality_score = data["quality_score"]
        self.multimodal = data.get("multimodal", False)
        self.supports_tools = data.get("supports_tools", True)
        self.notes = data.get("notes", "")
        self.auth_env = data.get("auth_env")
        self.base_url_env = data.get("base_url_env")

    @property
    def api_key(self) -> str | None:
        """Get API key from environment."""
        if not self.auth_env:
            return None
        return os.getenv(self.auth_env)

    @property
    def base_url(self) -> str | None:
        """Get base URL from environment."""
        if not self.base_url_env:
            return None
        return os.getenv(self.base_url_env)


class ModelRegistry:
    """Load and manage model configurations from YAML."""

    def __init__(self, config_path: Path | str):
        with open(config_path) as f:
            data = yaml.safe_load(f)

        self.models = {
            m["model_id"]: ModelConfig(m) for m in data["models"]
        }
        self.routing_config = data.get("routing", {})

    def get(self, model_id: str) -> ModelConfig | None:
        """Get model config by ID."""
        return self.models.get(model_id)

    def get_by_difficulty(self, difficulty: int) -> list[ModelConfig]:
        """Get all models matching difficulty level."""
        return [m for m in self.models.values() if m.difficulty == difficulty]

    def rank_by_cost(self, models: list[ModelConfig]) -> list[ModelConfig]:
        """Sort models by total cost (input + output), cheapest first."""
        return sorted(
            models,
            key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output
        )


class LiteLLMAdapter:
    """Adapter for LiteLLM with unified interface."""

    def __init__(self, registry: ModelRegistry):
        self.registry = registry
        # Disable LiteLLM's verbose logging
        litellm.suppress_debug_info = True
        litellm.set_verbose = False

    async def complete(
        self,
        model_id: str,
        messages: list[dict],
        config: LLMConfig,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Call LiteLLM completion with model from registry.

        Args:
            model_id: Model ID from registry (e.g., 'claude-sonnet-4')
            messages: OpenAI-format messages
            config: LLM configuration
            tools: Optional tool definitions

        Returns:
            LLMResponse with standardized format
        """
        model_config = self.registry.get(model_id)
        if not model_config:
            raise ValueError(f"Model {model_id} not in registry")

        # Build LiteLLM params
        params = {
            "model": model_config.litellm_name,
            "messages": messages,
            "max_tokens": config.max_tokens,
            "temperature": config.temperature,
        }

        # Add API key if needed
        if model_config.api_key:
            params["api_key"] = model_config.api_key

        # Add base URL for local models
        if model_config.base_url:
            params["api_base"] = model_config.base_url

        # Add tools if provided
        if tools and model_config.supports_tools:
            params["tools"] = tools

        try:
            # Call LiteLLM
            response = await acompletion(**params)

            # Extract response
            message = response.choices[0].message
            content = message.content or ""

            # Extract tool calls if present
            tool_calls = None
            if hasattr(message, "tool_calls") and message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "input": yaml.safe_load(tc.function.arguments),
                    }
                    for tc in message.tool_calls
                ]

            # Get usage stats
            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0

            # Calculate cost from registry
            cost_usd = (
                (input_tokens / 1_000_000) * model_config.cost_per_1m_input +
                (output_tokens / 1_000_000) * model_config.cost_per_1m_output
            )

            logger.debug(
                f"LiteLLM response: model={response.model}, "
                f"tokens={input_tokens}+{output_tokens}, "
                f"cost=${cost_usd:.4f}"
            )

            return LLMResponse(
                content=content,
                model=response.model,
                provider="litellm",  # Abstract away provider
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                tool_calls=tool_calls,
            )

        except Exception as e:
            logger.error(f"LiteLLM error for {model_id}: {e}")
            raise


def create_adapter() -> LiteLLMAdapter:
    """Create LiteLLM adapter with model registry."""
    from sentinel.core.config import get_settings

    settings = get_settings()
    config_path = settings.data_dir.parent / "src" / "sentinel" / "configs" / "models.yaml"

    registry = ModelRegistry(config_path)
    return LiteLLMAdapter(registry)
```

**2.2 Refactor Router** (`llm/router.py`)

Keep the task-aware logic, but use LiteLLMAdapter instead of custom providers:

```python
"""LLM provider router - task-aware model selection."""

from enum import Enum

from sentinel.core.logging import get_logger
from sentinel.llm.base import LLMConfig, LLMResponse
from sentinel.llm.litellm_adapter import LiteLLMAdapter, ModelRegistry, create_adapter

logger = get_logger("llm.router")


class TaskType(Enum):
    """Task categories for model selection."""
    CHAT = "chat"
    REASONING = "reasoning"
    SIMPLE = "simple"
    BACKGROUND = "background"
    SUMMARIZATION = "summarization"
    TOOL_CALL = "tool_call"
    INTER_AGENT = "inter_agent"
    FACT_EXTRACTION = "fact_extraction"
    IMPORTANCE_SCORING = "importance_scoring"


class SentinelLLMRouter:
    """Router with task-aware model selection using LiteLLM."""

    def __init__(self, adapter: LiteLLMAdapter):
        self.adapter = adapter
        self.registry = adapter.registry
        self._cost_tracker = None

        # Load task difficulty from config
        routing = self.registry.routing_config
        self.task_difficulty = routing.get("task_difficulty", {})
        self.budget_threshold = routing.get("budget_threshold", 0.8)

    def set_cost_tracker(self, tracker):
        """Set cost tracking service."""
        self._cost_tracker = tracker

    async def complete(
        self,
        messages: list[dict],
        config: LLMConfig,
        task: TaskType | None = None,
        tools: list[dict] | None = None,
    ) -> LLMResponse:
        """Route completion to optimal model based on task/cost."""

        # 1. Determine difficulty from task
        difficulty = self.task_difficulty.get(
            task.value if task else "simple", 2
        )

        # 2. Check budget - downgrade if approaching limit
        if self._cost_tracker and self._cost_tracker.should_use_cheaper_model():
            if difficulty > 1:
                original = difficulty
                difficulty = max(1, difficulty - 1)
                logger.info(
                    f"Budget at {self._cost_tracker.get_cost_summary()['percent_used']:.1f}%: "
                    f"downgraded difficulty {original} -> {difficulty}"
                )

        # 3. Get candidate models for this difficulty
        candidates = self.registry.get_by_difficulty(difficulty)

        if not candidates:
            # Fallback to easier difficulty
            if difficulty > 1:
                logger.warning(f"No models for difficulty {difficulty}, trying easier")
                return await self.complete(
                    messages, config, task=TaskType.SIMPLE, tools=tools
                )
            raise RuntimeError("No models available")

        # 4. Sort by cost (cheapest first)
        candidates = self.registry.rank_by_cost(candidates)

        # 5. Try each candidate in order
        last_error = None
        for model_config in candidates:
            try:
                response = await self.adapter.complete(
                    model_id=model_config.model_id,
                    messages=messages,
                    config=config,
                    tools=tools,
                )

                # Track cost
                if self._cost_tracker:
                    self._cost_tracker.add_cost(response.cost_usd)

                logger.info(
                    f"Task {task.value if task else 'default'}: "
                    f"used {response.model} (difficulty={difficulty}, "
                    f"cost=${response.cost_usd:.4f})"
                )
                return response

            except Exception as e:
                logger.warning(f"Model {model_config.model_id} failed: {e}")
                last_error = e
                continue

        # 6. All failed - try easier models as fallback
        if difficulty > 1:
            logger.warning("All models failed, trying easier difficulty")
            return await self.complete(
                messages, config, task=TaskType.SIMPLE, tools=tools
            )

        raise RuntimeError(f"All models failed. Last error: {last_error}")


def create_default_router() -> SentinelLLMRouter:
    """Create router with LiteLLM adapter and cost tracking."""
    from sentinel.llm.cost_tracker import CostTracker
    from sentinel.core.config import get_settings

    settings = get_settings()

    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)

    # Set up cost tracking
    cost_tracker = CostTracker(daily_limit=settings.daily_cost_limit)
    router.set_cost_tracker(cost_tracker)

    return router
```

### Phase 3: Update Base Types

**3.1 Simplify `llm/base.py`**

Remove provider-specific classes, keep only shared types:

```python
"""Base LLM types and interfaces."""

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    """LLM request configuration."""

    model: str | None  # Specific model override
    max_tokens: int
    temperature: float
    system_prompt: str | None = None


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    tool_calls: list[dict[str, Any]] | None = None
```

### Phase 4: Testing Strategy

**4.1 Create Test Fixtures**

```python
# tests/fixtures/llm.py
"""LLM test fixtures."""

import pytest
from sentinel.llm.litellm_adapter import ModelRegistry, LiteLLMAdapter
from pathlib import Path


@pytest.fixture
def model_registry():
    """Load test model registry."""
    config_path = Path(__file__).parent.parent.parent / "src" / "sentinel" / "configs" / "models.yaml"
    return ModelRegistry(config_path)


@pytest.fixture
def litellm_adapter(model_registry):
    """Create LiteLLM adapter with test registry."""
    return LiteLLMAdapter(model_registry)


@pytest.fixture
def sentinel_router(litellm_adapter):
    """Create Sentinel router for testing."""
    from sentinel.llm.router import SentinelLLMRouter
    return SentinelLLMRouter(litellm_adapter)
```

**4.2 Migration Tests** (`tests/test_litellm_migration.py`)

```python
"""Tests to verify LiteLLM migration correctness."""

import pytest
from sentinel.llm.router import TaskType, create_default_router
from sentinel.llm.base import LLMConfig


@pytest.mark.integration
async def test_router_task_based_selection(sentinel_router):
    """Test that router still selects models based on task difficulty."""
    messages = [{"role": "user", "content": "Hello"}]
    config = LLMConfig(model=None, max_tokens=100, temperature=0.7)

    # Hard task should use difficulty 3 model
    response = await sentinel_router.complete(
        messages, config, task=TaskType.REASONING
    )
    assert response.content
    assert response.cost_usd > 0

    # Simple task should use difficulty 1 model (cheaper)
    response_simple = await sentinel_router.complete(
        messages, config, task=TaskType.SIMPLE
    )
    assert response_simple.content
    # Should be cheaper than reasoning task
    assert response_simple.cost_usd < response.cost_usd


@pytest.mark.integration
async def test_vision_support_preserved(sentinel_router):
    """Test that multimodal/vision support still works."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": "What color is this?"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,..."}
            }
        ]
    }]
    config = LLMConfig(model=None, max_tokens=100, temperature=0.7)

    response = await sentinel_router.complete(messages, config, task=TaskType.CHAT)
    assert response.content


@pytest.mark.integration
async def test_tool_calling_preserved(sentinel_router):
    """Test that tool calling still works."""
    messages = [{"role": "user", "content": "What's the weather in London?"}]
    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }
    }]
    config = LLMConfig(model=None, max_tokens=100, temperature=0.7)

    response = await sentinel_router.complete(
        messages, config, task=TaskType.TOOL_CALL, tools=tools
    )
    assert response.tool_calls is not None
    assert len(response.tool_calls) > 0


@pytest.mark.integration
async def test_budget_downgrade_logic(sentinel_router):
    """Test that budget-based downgrade still works."""
    from sentinel.llm.cost_tracker import CostTracker

    # Set very low budget to trigger downgrade
    cost_tracker = CostTracker(daily_limit=0.01)
    sentinel_router.set_cost_tracker(cost_tracker)

    messages = [{"role": "user", "content": "Test"}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0.7)

    # First call - should work normally
    response1 = await sentinel_router.complete(
        messages, config, task=TaskType.REASONING
    )

    # Add cost to approach limit
    cost_tracker.add_cost(0.008)

    # Second call - should auto-downgrade
    response2 = await sentinel_router.complete(
        messages, config, task=TaskType.REASONING
    )

    # Should have used cheaper model
    assert response2.cost_usd < response1.cost_usd
```

**4.3 Compatibility Tests** (`tests/test_backward_compat.py`)

```python
"""Verify existing agent code works unchanged."""

import pytest
from sentinel.agents.dialog import DialogAgent
from sentinel.llm.router import create_default_router
from sentinel.memory.store import SQLiteMemoryStore
from sentinel.core.types import Message, ContentType
from datetime import datetime
from uuid import uuid4


@pytest.mark.integration
async def test_dialog_agent_unchanged():
    """Test that DialogAgent works with new router without changes."""
    router = create_default_router()
    memory = SQLiteMemoryStore(":memory:")
    await memory.connect()

    agent = DialogAgent(llm=router, memory=memory)
    await agent.initialize()

    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="Hello, how are you?",
        content_type=ContentType.TEXT,
    )

    response = await agent.process(message)
    assert response.content
    assert response.role == "assistant"

    await memory.close()
```

### Phase 5: Migration Execution

**5.1 Pre-migration Checklist**

- [ ] All existing tests passing
- [ ] Backup current implementation
- [ ] Create feature branch: `git checkout -b feat/litellm-migration`
- [ ] Document current behavior baseline

**5.2 Migration Steps**

1. Install LiteLLM: `uv add litellm`
2. Create `configs/models.yaml`
3. Implement `llm/litellm_adapter.py`
4. Refactor `llm/router.py` (keep file, replace internals)
5. Simplify `llm/base.py`
6. Delete obsolete files: `claude.py`, `openrouter.py`, `local.py`, `registry.py`
7. Update imports across codebase
8. Run tests: `uv run pytest -v`
9. Run integration tests: `uv run pytest tests/integration -v`
10. Manual testing with Telegram bot
11. Update documentation

**5.3 Rollback Plan**

If migration fails:
- Revert to main branch: `git checkout main`
- Migration is in separate branch, main unaffected
- No data loss risk (configuration only)

### Phase 6: Cleanup

**Files to Delete**:
- `src/sentinel/llm/claude.py` (replaced by LiteLLM)
- `src/sentinel/llm/openrouter.py` (replaced by LiteLLM)
- `src/sentinel/llm/local.py` (replaced by LiteLLM)
- `src/sentinel/llm/registry.py` (replaced by YAML config)

**Tests to Update**:
- `tests/integration/test_llm_providers.py` → test LiteLLM adapter instead
- All imports of old providers
- Mock providers in unit tests

**Documentation to Update**:
- README.md - LiteLLM installation
- Architecture docs - new LLM layer diagram
- Adding new models - edit YAML instead of Python

## Benefits Summary

**What We Gain**:
1. **100+ providers** supported out-of-box (vs our 3)
2. **Maintained pricing database** - no manual updates
3. **Battle-tested API translation** - handles edge cases we haven't hit yet
4. **Easier to add models** - YAML config vs Python code
5. **Future-proof** - LiteLLM tracks new providers/models
6. **Less code to maintain** - delete 3 provider implementations

**What We Keep**:
1. **Task-aware routing** - our semantic difficulty mapping
2. **Budget auto-downgrade** - clean cost control logic
3. **Simple architecture** - no proxy/Redis/PostgreSQL
4. **Full control** - can still override/customize
5. **Existing agent code** - unchanged, backward compatible

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| LiteLLM breaking change | High | Pin version, test before upgrade |
| Performance regression | Medium | Benchmark before/after, measure latency |
| Cost calculation drift | Low | Validate against known models |
| Tool calling format change | High | Comprehensive integration tests |
| Local model compatibility | Medium | Test Ollama integration thoroughly |

## Success Criteria

- [ ] All existing tests pass
- [ ] New LiteLLM tests pass
- [ ] Telegram bot works normally
- [ ] Vision support preserved
- [ ] Tool calling preserved
- [ ] Cost tracking accurate
- [ ] Budget downgrade works
- [ ] No performance regression (< 100ms added latency)
- [ ] Code coverage maintained (> 80%)

## Timeline Estimate

- Phase 1 (Setup): 30 min
- Phase 2 (Implementation): 2-3 hours
- Phase 3 (Base types): 30 min
- Phase 4 (Testing): 1-2 hours
- Phase 5 (Migration): 1 hour
- Phase 6 (Cleanup): 30 min

**Total: 6-8 hours** for complete migration with testing

## Questions to Resolve

1. **Should we use LiteLLM's Router or build our own?**
   - Recommendation: Build our own (SentinelLLMRouter) for task-awareness
   - Use LiteLLM only for `completion()` calls

2. **Keep cost tracking or use LiteLLM's?**
   - Recommendation: Keep ours (simpler, in-memory, has budget logic)
   - Use LiteLLM's pricing database for cost calculation

3. **YAML config location?**
   - Recommendation: `src/sentinel/configs/models.yaml`
   - Allows runtime edits without code changes

4. **Handle model deprecation?**
   - Recommendation: Add `deprecated: true` flag in YAML
   - Router skips deprecated models unless explicitly requested
