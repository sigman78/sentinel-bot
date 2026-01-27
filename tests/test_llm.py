"""Tests for LLM module."""

from sentinel.llm.base import LLMConfig, ProviderType
from sentinel.llm.router import LLMRouter, TaskType


def test_router_no_providers():
    """Router raises when no providers registered."""
    router = LLMRouter()
    assert len(router._providers) == 0


def test_router_fallback_order():
    """Router has correct fallback order."""
    router = LLMRouter()
    assert router._fallback_order == [
        ProviderType.CLAUDE,
        ProviderType.OPENROUTER,
        ProviderType.LOCAL,
    ]


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
    """TaskType enum has expected values."""
    assert TaskType.CHAT.value == "chat"
    assert TaskType.REASONING.value == "reasoning"
    assert TaskType.SIMPLE.value == "simple"
    assert TaskType.BACKGROUND.value == "background"


def test_router_available_providers():
    """Router tracks available providers."""
    router = LLMRouter()
    assert router.available_providers == []
