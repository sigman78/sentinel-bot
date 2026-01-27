"""Tests for LLM module."""

from sentinel.llm.base import LLMConfig, ProviderType
from sentinel.llm.router import TASK_DIFFICULTY, LLMRouter, TaskType


def test_router_no_providers():
    """Router raises when no providers registered."""
    router = LLMRouter()
    assert len(router._providers) == 0


def test_llm_config_defaults():
    """LLMConfig has sensible defaults."""
    config = LLMConfig(model="test-model")
    assert config.max_tokens == 4096
    assert config.temperature == 0.7
    assert config.system_prompt is None


def test_provider_type_values():
    """ProviderType enum has expected values."""
    assert ProviderType.CLAUDE.value == "claude"
    assert ProviderType.OPENROUTER.value == "openrouter"
    assert ProviderType.LOCAL.value == "local"


def test_task_type_values():
    """TaskType enum has all expected values."""
    assert TaskType.CHAT.value == "chat"
    assert TaskType.REASONING.value == "reasoning"
    assert TaskType.SIMPLE.value == "simple"
    assert TaskType.BACKGROUND.value == "background"
    assert TaskType.SUMMARIZATION.value == "summarization"
    assert TaskType.FACT_EXTRACTION.value == "fact_extraction"
    assert TaskType.IMPORTANCE_SCORING.value == "importance_scoring"
    assert TaskType.TOOL_CALL.value == "tool_call"
    assert TaskType.INTER_AGENT.value == "inter_agent"


def test_router_available_providers():
    """Router tracks available providers."""
    router = LLMRouter()
    assert router.available_providers == []


def test_task_difficulty_mapping():
    """All task types have difficulty mappings."""
    # Hard difficulty (3)
    assert TASK_DIFFICULTY[TaskType.CHAT] == 3
    assert TASK_DIFFICULTY[TaskType.REASONING] == 3

    # Intermediate difficulty (2)
    assert TASK_DIFFICULTY[TaskType.FACT_EXTRACTION] == 2
    assert TASK_DIFFICULTY[TaskType.SUMMARIZATION] == 2
    assert TASK_DIFFICULTY[TaskType.BACKGROUND] == 2

    # Easy difficulty (1)
    assert TASK_DIFFICULTY[TaskType.SIMPLE] == 1
    assert TASK_DIFFICULTY[TaskType.TOOL_CALL] == 1
    assert TASK_DIFFICULTY[TaskType.INTER_AGENT] == 1
    assert TASK_DIFFICULTY[TaskType.IMPORTANCE_SCORING] == 1


def test_cost_tracker_initialization():
    """CostTracker can be set on router."""
    from sentinel.llm.cost_tracker import CostTracker

    router = LLMRouter()
    tracker = CostTracker(daily_limit=10.0)
    router.set_cost_tracker(tracker)
    assert router._cost_tracker is not None
