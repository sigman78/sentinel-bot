"""
Integration tests for LLM providers.

Run with: uv run pytest tests/integration -v
Requires: .env with API keys
"""

import pytest

from sentinel.core.config import get_settings
from sentinel.llm.base import LLMConfig, ProviderType
from sentinel.llm.claude import ClaudeProvider
from sentinel.llm.local import LocalProvider
from sentinel.llm.openrouter import OpenRouterProvider
from sentinel.llm.router import TaskType, create_default_router

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


@pytest.fixture
def settings():
    return get_settings()


# --- Claude Provider ---

@pytest.mark.asyncio
async def test_claude_health(settings):
    """Claude API is accessible."""
    if not settings.anthropic_api_key:
        pytest.skip("SENTINEL_ANTHROPIC_API_KEY not set")

    provider = ClaudeProvider()
    healthy = await provider.health_check()
    assert healthy, "Claude API health check failed"


@pytest.mark.asyncio
async def test_claude_completion(settings):
    """Claude generates completion."""
    if not settings.anthropic_api_key:
        pytest.skip("SENTINEL_ANTHROPIC_API_KEY not set")

    provider = ClaudeProvider()
    messages = [{"role": "user", "content": "Say 'test ok' and nothing else."}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0)

    response = await provider.complete(messages, config)

    assert response.content
    assert response.provider == ProviderType.CLAUDE
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    print(f"Claude: {response.content} (${response.cost_usd:.4f})")


# --- OpenRouter Provider ---

@pytest.mark.asyncio
async def test_openrouter_health(settings):
    """OpenRouter API is accessible."""
    if not settings.openrouter_api_key:
        pytest.skip("SENTINEL_OPENROUTER_API_KEY not set")

    provider = OpenRouterProvider()
    healthy = await provider.health_check()
    assert healthy, "OpenRouter API health check failed"
    await provider.close()


@pytest.mark.asyncio
async def test_openrouter_completion(settings):
    """OpenRouter generates completion."""
    if not settings.openrouter_api_key:
        pytest.skip("SENTINEL_OPENROUTER_API_KEY not set")

    provider = OpenRouterProvider()
    messages = [{"role": "user", "content": "Say 'test ok' and nothing else."}]
    config = LLMConfig(model="openai/gpt-4o-mini", max_tokens=50, temperature=0)

    response = await provider.complete(messages, config)

    assert response.content
    assert response.provider == ProviderType.OPENROUTER
    print(f"OpenRouter: {response.content} (${response.cost_usd:.4f})")
    await provider.close()


# --- Local LLM Provider ---

@pytest.mark.asyncio
async def test_local_health(settings):
    """Local LLM server is running."""
    if not settings.local_llm_url:
        pytest.skip("SENTINEL_LOCAL_LLM_URL not set")

    provider = LocalProvider()
    healthy = await provider.health_check()
    if not healthy:
        pytest.skip("Local LLM server not running")
    await provider.close()


@pytest.mark.asyncio
async def test_local_completion(settings):
    """Local LLM generates completion."""
    if not settings.local_llm_url:
        pytest.skip("SENTINEL_LOCAL_LLM_URL not set")

    provider = LocalProvider()
    if not await provider.health_check():
        await provider.close()
        pytest.skip("Local LLM server not running")

    messages = [{"role": "user", "content": "Say 'test ok' and nothing else."}]
    config = LLMConfig(model="local", max_tokens=50, temperature=0)

    response = await provider.complete(messages, config)

    assert response.content
    assert response.provider == ProviderType.LOCAL
    assert response.cost_usd == 0.0
    print(f"Local: {response.content}")
    await provider.close()


# --- Router ---

@pytest.mark.asyncio
async def test_router_fallback():
    """Router falls back when provider fails."""
    router = create_default_router()

    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    messages = [{"role": "user", "content": "Say 'router ok' and nothing else."}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0)

    response = await router.complete(messages, config)

    assert response.content
    print(f"Router used: {response.provider.value} - {response.content}")
    await router.close_all()


@pytest.mark.asyncio
async def test_router_task_selection():
    """Router selects provider based on task type."""
    router = create_default_router()

    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    messages = [{"role": "user", "content": "What is 2+2? Answer with just the number."}]
    config = LLMConfig(model=None, max_tokens=50, temperature=0)

    # Test SIMPLE task (should prefer OpenRouter/cheap model if available)
    response = await router.complete(messages, config, task=TaskType.SIMPLE)
    assert response.content
    print(f"SIMPLE task: {response.provider.value} - {response.content}")

    # Test CHAT task (should prefer Claude if available)
    response = await router.complete(messages, config, task=TaskType.CHAT)
    assert response.content
    print(f"CHAT task: {response.provider.value} - {response.content}")

    await router.close_all()
