"""Tool registry for managing available tools."""

from sentinel.core.logging import get_logger
from sentinel.tools.base import Tool

logger = get_logger("tools.registry")


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        if tool.name in self._tools:
            logger.warning(f"Tool {tool.name} already registered, overwriting")
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Tool | None:
        """Get tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_context_string(self) -> str:
        """
        Generate formatted tool definitions for LLM context.

        Returns:
            Multi-line string with all tool definitions
        """
        if not self._tools:
            return "No tools available."

        lines = ["# AVAILABLE TOOLS\n"]
        lines.append("You have access to the following tools:\n")

        for tool in self._tools.values():
            lines.append(tool.to_context_string())
            lines.append("")  # Blank line between tools

        lines.append(
            """
# TOOL USAGE

When you need to use a tool, output a JSON block:

```json
{
    "tool": "tool_name",
    "args": {
        "param1": "value1",
        "param2": "value2"
    }
}
```

You can call multiple tools by outputting multiple JSON blocks.
After tool execution, you'll receive results and can respond naturally to the user.
"""
        )

        return "\n".join(lines)

    def has_tool(self, name: str) -> bool:
        """Check if tool exists."""
        return name in self._tools

    def to_openai_tools(self) -> list[dict]:
        """
        Get all tools in OpenAI function calling format.

        Returns:
            List of tools in OpenAI format
        """
        return [tool.to_openai_function() for tool in self._tools.values()]

    def to_anthropic_tools(self) -> list[dict]:
        """
        Get all tools in Anthropic tool use format.

        Returns:
            List of tools in Anthropic format
        """
        return [tool.to_anthropic_tool() for tool in self._tools.values()]


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_global_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: Tool) -> None:
    """Register a tool with the global registry."""
    registry = get_global_registry()
    registry.register(tool)
