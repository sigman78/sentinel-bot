"""Agent delegation tool - allows DialogAgent to delegate to specialized tool agents."""

from sentinel.core.tool_agent_registry import get_tool_agent_registry
from sentinel.core.types import ActionResult
from sentinel.tools.base import tool
from sentinel.tools.registry import register_tool

# Global storage for user profile (set by DialogAgent)
_current_user_profile = None


def set_current_user_profile(profile):
    """Set current user profile for delegation context."""
    global _current_user_profile
    _current_user_profile = profile


@tool(
    "delegate_to_agent",
    """Delegate a task to a specialized agent for focused execution.

Use this when you need specialized capabilities like weather information, web search, etc.
The specialized agent will handle the task efficiently and return a natural language result.

When to use:
- Weather queries → delegate to WeatherAgent
- Tasks that match a specialized agent's capabilities

Choose the appropriate agent based on the available agents list in your context.""",
    examples=[
        'delegate_to_agent(agent_name="WeatherAgent", task="what\'s the weather in Paris?")',
        'delegate_to_agent(agent_name="WeatherAgent", task="will it rain today?")',
    ],
)
async def delegate_to_agent(agent_name: str, task: str) -> ActionResult:
    """Delegate a task to a specialized tool agent.

    Args:
        agent_name: Name of the specialized agent (e.g., 'WeatherAgent')
        task: Natural language task description for the agent

    Returns:
        ActionResult with agent's response or error
    """
    try:
        registry = get_tool_agent_registry()

        # Build global context
        global_context = {}
        if _current_user_profile:
            global_context["user_profile"] = _current_user_profile

        # Delegate
        result = await registry.delegate(agent_name, task, global_context)

        return ActionResult(
            success=True,
            data={"result": result, "agent": agent_name},
        )

    except ValueError as e:
        # Agent not found
        return ActionResult(success=False, data=None, error=str(e))
    except Exception as e:
        # Execution error
        return ActionResult(
            success=False, data=None, error=f"Delegation failed: {str(e)}"
        )


def register_delegation_tools() -> None:
    """Register delegation tools with the global registry."""
    register_tool(delegate_to_agent._tool)  # type: ignore
