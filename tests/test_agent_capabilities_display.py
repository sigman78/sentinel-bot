"""Test what capability descriptions Claude sees for agent selection."""

from sentinel.core.tool_agent_registry import ToolAgentRegistry
from sentinel.agents.agentic_cli import AgenticCliAgent
from sentinel.configs.curl_agent import config as http_agent_config
from sentinel.configs.file_agent import config as file_agent_config


def test_capabilities_summary_display():
    """Test the capabilities summary that gets shown to Claude."""
    registry = ToolAgentRegistry()

    # Register both agents
    http_agent = AgenticCliAgent(config=http_agent_config, llm=None, working_dir=".")
    file_agent = AgenticCliAgent(config=file_agent_config, llm=None, working_dir=".")

    registry.register(http_agent)
    registry.register(file_agent)

    # Get the capabilities summary
    summary = registry.get_capabilities_summary()

    print("\n" + "="*80)
    print("CAPABILITIES SUMMARY (what Claude sees):")
    print("="*80)
    print(summary)
    print("="*80 + "\n")

    # Verify both agents are listed
    assert "HttpAgent" in summary
    assert "FileAgent" in summary

    # Verify descriptions are present
    assert "HTTP" in summary or "curl" in summary
    assert "file" in summary.lower() or "directory" in summary.lower()


if __name__ == "__main__":
    test_capabilities_summary_display()
