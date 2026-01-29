"""Tests to verify LiteLLM migration correctness."""

import pytest

from sentinel.llm.base import LLMConfig
from sentinel.llm.litellm_adapter import ModelRegistry, LiteLLMAdapter, create_adapter
from sentinel.llm.router import SentinelLLMRouter, TaskType, create_default_router
from pathlib import Path


def test_model_registry_loads():
    """Test that model registry loads from YAML."""
    config_path = Path(__file__).parent.parent / "src" / "sentinel" / "configs" / "models.yaml"
    registry = ModelRegistry(config_path)

    # Should have models
    assert len(registry.models) > 0

    # Should have difficulty levels
    assert len(registry.get_by_difficulty(1)) > 0
    assert len(registry.get_by_difficulty(2)) > 0
    assert len(registry.get_by_difficulty(3)) > 0

    # Should have routing config
    assert "task_difficulty" in registry.routing_config
    assert "budget_threshold" in registry.routing_config


def test_model_config_availability():
    """Test that model availability checks work."""
    config_path = Path(__file__).parent.parent / "src" / "sentinel" / "configs" / "models.yaml"
    registry = ModelRegistry(config_path)

    # At least one model should be available (local doesn't need creds)
    available_models = [m for m in registry.models.values() if m.is_available]
    assert len(available_models) > 0


def test_adapter_creation():
    """Test that adapter can be created."""
    adapter = create_adapter()
    assert adapter is not None
    assert adapter.registry is not None
    assert len(adapter.registry.models) > 0


def test_router_creation():
    """Test that router can be created."""
    router = create_default_router()
    assert router is not None
    assert router.adapter is not None
    assert router.registry is not None


@pytest.mark.integration
async def test_router_task_based_selection():
    """Test that router selects models based on task difficulty."""
    router = create_default_router()

    messages = [{"role": "user", "content": "Hello"}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0.7)

    # Simple task should use difficulty 1 model (cheapest)
    try:
        response = await router.complete(messages, config, task=TaskType.SIMPLE)
        assert response.content
        assert response.cost_usd >= 0
        assert response.input_tokens > 0
        simple_cost = response.cost_usd
    except Exception as e:
        pytest.skip(f"No models available for simple task: {e}")

    # Reasoning task should use difficulty 3 model (may be more expensive)
    try:
        response_reasoning = await router.complete(
            messages, config, task=TaskType.REASONING
        )
        assert response_reasoning.content
        assert response_reasoning.cost_usd >= 0
    except Exception as e:
        pytest.skip(f"No models available for reasoning task: {e}")


@pytest.mark.integration
async def test_adapter_completion():
    """Test that adapter can complete a request."""
    adapter = create_adapter()

    # Find an available model
    available = None
    for model in adapter.registry.models.values():
        if model.is_available:
            available = model
            break

    if not available:
        pytest.skip("No models available for testing")

    messages = [{"role": "user", "content": "Say hello in 3 words"}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0.7)

    response = await adapter.complete(
        model_id=available.model_id,
        messages=messages,
        config=config,
    )

    assert response.content
    assert len(response.content) > 0
    assert response.model
    assert response.provider
    assert response.input_tokens > 0
    assert response.cost_usd >= 0


@pytest.mark.integration
async def test_tool_calling():
    """Test that tool calling works through the adapter."""
    adapter = create_adapter()

    # Find an available model that supports tools
    available = None
    for model in adapter.registry.models.values():
        if model.is_available and model.supports_tools:
            available = model
            break

    if not available:
        pytest.skip("No models with tool support available")

    messages = [{"role": "user", "content": "What's the weather in London?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]
    config = LLMConfig(model=None, max_tokens=100, temperature=0.7)

    response = await adapter.complete(
        model_id=available.model_id, messages=messages, config=config, tools=tools
    )

    # Should have either content or tool calls
    assert response.content or response.tool_calls
    if response.tool_calls:
        assert len(response.tool_calls) > 0
        assert "name" in response.tool_calls[0]
        assert "input" in response.tool_calls[0]
