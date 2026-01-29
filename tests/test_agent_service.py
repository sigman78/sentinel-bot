"""Tests for agent service initialization."""

import pytest

from sentinel.configs import CLI_AGENT_CONFIGS
from sentinel.core.agent_service import initialize_agents
from sentinel.core.tool_agent_registry import ToolAgentRegistry


def test_cli_agent_configs_list():
    """Test that CLI_AGENT_CONFIGS list is properly defined."""
    # Should have at least FileAgent and HttpAgent
    assert len(CLI_AGENT_CONFIGS) >= 2

    # Check that expected agents are in the list
    config_names = [c.name for c in CLI_AGENT_CONFIGS]
    assert "FileAgent" in config_names
    assert "HttpAgent" in config_names

    # Verify all items are valid configs
    for config in CLI_AGENT_CONFIGS:
        assert hasattr(config, 'name')
        assert hasattr(config, 'description')
        assert hasattr(config, 'tools')
        assert len(config.tools) > 0


def test_initialize_agents():
    """Test that initialize_agents creates and registers all agents."""
    # Create a mock LLM (None is acceptable for registry testing)
    registry = ToolAgentRegistry()

    # Initialize agents (will use None as LLM, which is fine for structure testing)
    initialized_registry = initialize_agents(
        cheap_llm=None,
        working_dir=".",
        registry=registry,
    )

    # Should return the same registry
    assert initialized_registry is registry

    # Should have registered WeatherAgent + discovered CLI agents
    registered_agents = list(initialized_registry._agents.keys())
    assert "WeatherAgent" in registered_agents
    assert "FileAgent" in registered_agents
    assert "HttpAgent" in registered_agents

    # Check capabilities summary
    capabilities = registry.get_capabilities_summary()
    assert "WeatherAgent" in capabilities
    assert "FileAgent" in capabilities
    assert "HttpAgent" in capabilities


def test_initialize_agents_creates_new_registry():
    """Test that initialize_agents creates new registry if none provided."""
    result = initialize_agents(
        cheap_llm=None,
        working_dir=".",
        registry=None,  # Should create a new one
    )

    # Should return a registry
    assert isinstance(result, ToolAgentRegistry)

    # Should have agents registered
    assert len(result._agents) >= 3  # WeatherAgent + FileAgent + HttpAgent


def test_agent_configs_have_distinct_descriptions():
    """Test that CLI agent configs have distinct descriptions."""
    descriptions = [c.description for c in CLI_AGENT_CONFIGS]

    # Should all be different
    assert len(descriptions) == len(set(descriptions))

    # Should all be non-empty
    assert all(len(d) > 0 for d in descriptions)
