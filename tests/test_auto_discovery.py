"""Test agent configuration registration pattern."""

from sentinel.agents.agentic_cli import AgenticCliConfig, CliTool, SafetyLimits
from sentinel.configs import CLI_AGENT_CONFIGS


def test_cli_configs_list_structure():
    """Test that CLI_AGENT_CONFIGS is a proper list of configs."""
    # Should be a list
    assert isinstance(CLI_AGENT_CONFIGS, list)

    # Should have at least the known agents
    config_names = {c.name for c in CLI_AGENT_CONFIGS}
    assert "FileAgent" in config_names
    assert "HttpAgent" in config_names


def test_config_imports():
    """Test that individual config modules can be imported."""
    from sentinel.configs import file_agent, curl_agent

    # Verify they have config attribute
    assert hasattr(file_agent, 'config')
    assert hasattr(curl_agent, 'config')

    # Verify configs are of correct type
    assert isinstance(file_agent.config, AgenticCliConfig)
    assert isinstance(curl_agent.config, AgenticCliConfig)

    # Verify names match
    assert file_agent.config.name == "FileAgent"
    assert curl_agent.config.name == "HttpAgent"


def test_new_config_pattern():
    """Demonstrate the pattern for adding new agents."""
    # To add a new agent:
    # 1. Create src/sentinel/configs/my_agent.py with this pattern:

    example_config = AgenticCliConfig(
        name="ExampleAgent",
        description="I am an example agent demonstrating the pattern",
        tools=[
            CliTool(
                name="example",
                command="echo",
                help_text="Example command",
                examples=["echo hello"],
            ),
        ],
        limits=SafetyLimits(),
    )

    # 2. Import it in configs/__init__.py:
    #    from sentinel.configs.my_agent import config as example_config
    #
    # 3. Add to CLI_AGENT_CONFIGS list:
    #    CLI_AGENT_CONFIGS = [
    #        http_agent_config,
    #        file_agent_config,
    #        example_config,  # <-- Add here
    #    ]

    # Verify the example has required attributes
    assert hasattr(example_config, 'name')
    assert hasattr(example_config, 'description')
    assert hasattr(example_config, 'tools')
    assert isinstance(example_config, AgenticCliConfig)
