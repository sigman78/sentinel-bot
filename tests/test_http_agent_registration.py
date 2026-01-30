"""Test that HttpAgent is properly registered and chosen for HTTP tasks."""

from sentinel.core.tool_agent_registry import ToolAgentRegistry
from sentinel.agents.agentic_cli import AgenticCliAgent
from sentinel.tools.decl.curl_agent import config as http_agent_config
from sentinel.tools.decl.file_agent import config as file_agent_config


def test_http_agent_config():
    """Test that HttpAgent config is properly defined."""
    assert http_agent_config.name == "HttpAgent"
    assert "HTTP" in http_agent_config.description or "curl" in http_agent_config.description
    assert len(http_agent_config.tools) > 0
    assert http_agent_config.tools[0].name == "curl"


def test_http_agent_registration():
    """Test that HttpAgent can be registered in the registry."""
    registry = ToolAgentRegistry()

    # Create and register HttpAgent
    http_agent = AgenticCliAgent(config=http_agent_config, llm=None, working_dir=".")
    registry.register(http_agent)

    # Verify it's registered
    assert "HttpAgent" in registry._agents

    # Check capabilities summary includes HttpAgent
    capabilities = registry.get_capabilities_summary()
    assert "HttpAgent" in capabilities
    assert "HTTP" in capabilities or "curl" in capabilities


def test_http_vs_file_agent_descriptions():
    """Test that HttpAgent and FileAgent have distinct descriptions."""
    http_desc = http_agent_config.description
    file_desc = file_agent_config.description

    # HttpAgent should mention HTTP/web/curl
    assert any(keyword in http_desc.lower() for keyword in ["http", "web", "curl", "api"])

    # FileAgent should mention files/directories
    assert any(keyword in file_desc.lower() for keyword in ["file", "directory", "directories"])

    # They shouldn't overlap too much
    assert http_desc != file_desc
