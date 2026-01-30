"""Tests for LLM module."""

from sentinel.llm.base import LLMConfig
from sentinel.llm.litellm_adapter import create_adapter
from sentinel.llm.router import SentinelLLMRouter, TaskType


def test_llm_config_defaults():
    """LLMConfig has sensible defaults."""
    config = LLMConfig(model="test-model")
    assert config.max_tokens == 4096
    assert config.temperature == 0.7
    assert config.system_prompt is None


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


def test_router_task_difficulty_mapping():
    """Router loads task difficulty from config."""
    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)

    # Should have task difficulty mapping from YAML
    assert "chat" in router.task_difficulty
    assert "reasoning" in router.task_difficulty
    assert "simple" in router.task_difficulty

    # Hard difficulty (3)
    assert router.task_difficulty["chat"] == 3
    assert router.task_difficulty["reasoning"] == 3

    # Intermediate difficulty (2)
    assert router.task_difficulty["fact_extraction"] == 2
    assert router.task_difficulty["summarization"] == 2
    assert router.task_difficulty["background"] == 2

    # Easy difficulty (1)
    assert router.task_difficulty["simple"] == 1
    assert router.task_difficulty["tool_call"] == 1
    assert router.task_difficulty["inter_agent"] == 1
    assert router.task_difficulty["importance_scoring"] == 1


def test_cost_tracker_initialization():
    """CostTracker can be set on router."""
    from sentinel.llm.cost_tracker import CostTracker

    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)
    tracker = CostTracker(daily_limit=10.0)
    router.set_cost_tracker(tracker)
    assert router._cost_tracker is not None


def test_router_registry_access():
    """Router has access to model registry."""
    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)

    assert router.registry is not None
    assert len(router.registry.models) > 0


def test_router_model_selection_by_difficulty():
    """Router can get models by difficulty."""
    adapter = create_adapter()
    router = SentinelLLMRouter(adapter)

    # Should have models for each difficulty level
    easy_models = router.registry.get_by_difficulty(1)
    medium_models = router.registry.get_by_difficulty(2)
    hard_models = router.registry.get_by_difficulty(3)

    # Should have at least one model per difficulty (if credentials available)
    # This test only verifies structure, not availability
    assert isinstance(easy_models, list)
    assert isinstance(medium_models, list)
    assert isinstance(hard_models, list)
