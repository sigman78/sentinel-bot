"""Integration tests for tool agents and delegation."""

import pytest

from sentinel.agents.tool_agents.weather import WeatherAgent
from sentinel.core.tool_agent_registry import ToolAgentRegistry
from sentinel.llm.router import create_default_router


@pytest.mark.integration
async def test_weather_agent_basic():
    """Test WeatherAgent can fetch and summarize weather."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = WeatherAgent(llm=llm)

    # Test with explicit location
    result = await agent.execute_task("What's the weather in London?", {})

    assert isinstance(result, str)
    assert len(result) > 0
    assert "London" in result or "london" in result.lower()
    print(f"\nWeather result: {result}")


@pytest.mark.integration
async def test_tool_agent_registry():
    """Test ToolAgentRegistry registration and delegation."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    registry = ToolAgentRegistry()

    # Register WeatherAgent
    weather_agent = WeatherAgent(llm=llm)
    registry.register(weather_agent)

    # Check registration
    assert "WeatherAgent" in registry.list_agents()
    assert weather_agent == registry.get_agent("WeatherAgent")

    # Test capabilities summary
    capabilities = registry.get_capabilities_summary()
    assert "WeatherAgent" in capabilities
    assert "weather" in capabilities.lower()

    # Test delegation
    result = await registry.delegate("WeatherAgent", "weather in Tokyo", global_context={})

    assert isinstance(result, str)
    assert len(result) > 0
    print(f"\nDelegation result: {result}")


@pytest.mark.integration
async def test_weather_agent_with_user_location():
    """Test WeatherAgent uses user location from global context."""
    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = WeatherAgent(llm=llm)

    # Mock user profile with location
    from sentinel.memory.profile import UserProfile

    user_profile = UserProfile(name="TestUser", environment="Berlin, Germany")
    global_context = {"user_profile": user_profile}

    # Test with implicit location (should use user's location)
    result = await agent.execute_task("What's the weather today?", global_context)

    assert isinstance(result, str)
    assert len(result) > 0
    # Should mention Berlin or use IP-based location
    print(f"\nWeather with context: {result}")


@pytest.mark.integration
async def test_weather_agent_error_handling():
    """Test WeatherAgent handles errors gracefully."""
    from datetime import datetime
    from uuid import uuid4

    from sentinel.core.types import ContentType, Message

    router = create_default_router()
    if not router.available_providers:
        pytest.skip("No LLM providers configured")

    llm = router
    agent = WeatherAgent(llm=llm)

    # Test with invalid location using process() which catches exceptions
    message = Message(
        id=str(uuid4()),
        timestamp=datetime.now(),
        role="user",
        content="weather in INVALIDCITYXYZ123",
        content_type=ContentType.TEXT,
        metadata={"global_context": {}},
    )

    result = await agent.process(message)

    # Should return error message, not raise exception
    assert isinstance(result.content, str)
    assert "error" in result.content.lower() or "invalid" in result.content.lower()
    assert result.metadata.get("error") is True
