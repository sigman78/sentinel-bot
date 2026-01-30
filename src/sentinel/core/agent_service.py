"""Agent service initialization and registration.

Handles service-level agent setup, registering all specialized agents
with appropriate LLMs.
"""

from pathlib import Path

from sentinel.agents.agentic_cli import AgenticCliAgent
from sentinel.agents.base import LLMProvider
from sentinel.agents.tool_agents.weather import WeatherAgent
from sentinel.core.logging import get_logger
from sentinel.core.tool_agent_registry import ToolAgentRegistry, get_tool_agent_registry
from sentinel.tools.decl import CLI_AGENT_CONFIGS

logger = get_logger("core.agent_service")


def initialize_agents(
    cheap_llm: LLMProvider,
    working_dir: str | Path,
    registry: ToolAgentRegistry | None = None,
) -> ToolAgentRegistry:
    """Initialize and register all specialized agents.

    Registers CLI agent configs from sentinel.configs along with
    hardcoded agents (like WeatherAgent).

    Args:
        cheap_llm: LLM provider for sub-agents (prioritize cost savings)
        working_dir: Working directory for CLI agents
        registry: Optional existing registry (creates new if None)

    Returns:
        ToolAgentRegistry with all agents registered
    """
    if registry is None:
        registry = get_tool_agent_registry()

    working_dir = str(working_dir)

    # Register hardcoded ToolAgents
    weather_agent = WeatherAgent(llm=cheap_llm)
    registry.register(weather_agent)
    logger.info("Registered WeatherAgent")

    # Register CLI agents from configs list
    for config in CLI_AGENT_CONFIGS:
        try:
            agent = AgenticCliAgent(
                config=config,
                llm=cheap_llm,
                working_dir=working_dir,
            )
            registry.register(agent)
            logger.info(f"Registered {config.name}")
        except Exception as e:
            logger.error(f"Failed to register {config.name}: {e}")

    # Log summary
    capabilities = registry.get_capabilities_summary()
    logger.info(f"Agent initialization complete. {capabilities}")

    return registry
