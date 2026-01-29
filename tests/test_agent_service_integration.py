"""Integration test for agent service with real LLM providers."""

import pytest

from sentinel.core.agent_service import initialize_agents
from sentinel.llm.router import create_default_router


@pytest.mark.integration
async def test_initialize_agents_with_real_llm():
    """Test agent initialization with actual LLM providers."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    # Use the router as the LLM provider (it auto-selects models)
    llm = router

    # Initialize agents
    registry = initialize_agents(
        cheap_llm=llm,
        working_dir=".",
    )

    # Verify agents are registered
    assert "WeatherAgent" in registry._agents
    assert "FileAgent" in registry._agents
    assert "HttpAgent" in registry._agents

    # Verify capabilities summary
    capabilities = registry.get_capabilities_summary()
    print("\n" + "="*80)
    print("AGENT CAPABILITIES (auto-discovered):")
    print("="*80)
    print(capabilities)
    print("="*80 + "\n")

    # Check that each agent is described
    assert "WeatherAgent" in capabilities
    assert "FileAgent" in capabilities
    assert "HttpAgent" in capabilities
    assert "weather" in capabilities.lower()
    assert "file" in capabilities.lower()
    assert "http" in capabilities.lower() or "curl" in capabilities.lower()
