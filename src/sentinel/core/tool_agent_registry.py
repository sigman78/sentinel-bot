"""Tool agent registry - manages pool of specialized agents."""

from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from sentinel.core.logging import get_logger
from sentinel.core.types import ContentType, Message

logger = get_logger("core.tool_agent_registry")


class ToolAgentProtocol(Protocol):
    """Minimal protocol for tool agents registered in the registry."""

    agent_name: str

    def get_capability_description(self) -> str:
        ...

    async def process(self, message: Message) -> Message:
        ...


class ToolAgentRegistry:
    """Registry for tool agents initialized at startup.

    Manages a pool of specialized agents (both stateless ToolAgents and
    stateful AgenticCliAgents) that can be delegated tasks by higher-level
    agents (like DialogAgent).

    Registered agents must have:
    - agent_name: str
    - get_capability_description() -> str
    - process(message: Message) -> Message
    """

    def __init__(self) -> None:
        self._agents: dict[str, ToolAgentProtocol] = {}

    def register(self, agent: ToolAgentProtocol) -> None:
        """Register a specialized agent.

        Args:
            agent: Agent instance (ToolAgent, AgenticCliAgent, etc.)
        """
        if not hasattr(agent, "agent_name"):
            raise ValueError("Agent must have 'agent_name' attribute")
        if not hasattr(agent, "get_capability_description"):
            raise ValueError("Agent must have 'get_capability_description' method")
        if not hasattr(agent, "process"):
            raise ValueError("Agent must have 'process' method")

        agent_name = agent.agent_name
        if agent_name in self._agents:
            logger.warning(f"Agent {agent_name} already registered, replacing")

        self._agents[agent_name] = agent
        logger.info(f"Registered agent: {agent_name}")

    def get_agent(self, agent_name: str) -> ToolAgentProtocol | None:
        """Get agent by name.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(agent_name)

    def list_agents(self) -> list[str]:
        """Get list of registered agent names.

        Returns:
            List of agent names
        """
        return list(self._agents.keys())

    def get_capabilities_summary(self) -> str:
        """Generate natural language summary of available tool agents.

        This summary is injected into parent agent context so they know
        what specialized agents are available for delegation.

        Returns:
            Natural language capability list
        """
        if not self._agents:
            return "(No specialized agents available)"

        lines = ["Available specialized agents:"]
        for agent in self._agents.values():
            capability = agent.get_capability_description()
            lines.append(f"- {agent.agent_name}: {capability}")

        return "\n".join(lines)

    async def delegate(
        self, agent_name: str, task: str, global_context: dict[str, Any] | None = None
    ) -> str:
        """Delegate a task to a specific tool agent.

        Args:
            agent_name: Name of the agent to delegate to
            task: Natural language task description
            global_context: Shared context (user_profile, etc.)

        Returns:
            Natural language result from the tool agent

        Raises:
            ValueError: If agent not found
            Exception: On execution failure
        """
        agent = self._agents.get(agent_name)
        if not agent:
            available = ", ".join(self._agents.keys())
            raise ValueError(
                f"Tool agent '{agent_name}' not found. Available: {available}"
            )

        logger.info(f"Delegating to {agent_name}: {task[:100]}")

        # Package task as Message
        message = Message(
            id=str(uuid4()),
            timestamp=datetime.now(),
            role="user",
            content=task,
            content_type=ContentType.TEXT,
            metadata={"global_context": global_context or {}},
        )

        # Execute (stateless, single-call)
        response = await agent.process(message)

        if response.metadata.get("error"):
            logger.warning(f"{agent_name} returned error: {response.content}")

        return response.content


# Global registry instance
_global_registry: ToolAgentRegistry | None = None


def get_tool_agent_registry() -> ToolAgentRegistry:
    """Get or create global tool agent registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolAgentRegistry()
    return _global_registry
