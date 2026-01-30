"""Execute parsed tool calls."""

import json
from datetime import datetime
from typing import Any

from sentinel.core.logging import get_logger
from sentinel.core.types import ActionResult
from sentinel.tools.parser import ToolCall
from sentinel.tools.registry import ToolRegistry

logger = get_logger("tools.executor")

# Maximum length for logged content (characters)
MAX_LOG_LENGTH = 500


def _truncate_for_logging(result: ActionResult, max_len: int = MAX_LOG_LENGTH) -> str:
    """
    Create a truncated string representation of ActionResult for logging.

    Args:
        result: ActionResult to represent
        max_len: Maximum length of content fields

    Returns:
        Truncated string representation
    """
    if not result.success:
        # Errors are usually short, log them fully
        return repr(result)

    if not result.data:
        return "ActionResult(success=True, data=None)"

    # Truncate long content fields
    truncated_data = {}
    for key, value in result.data.items():
        if isinstance(value, str) and len(value) > max_len:
            truncated_data[key] = f"{value[:max_len]}... [truncated, {len(value)} chars total]"
        else:
            truncated_data[key] = value

    return f"ActionResult(success=True, data={truncated_data})"


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that handles datetime objects."""

    def default(self, obj: object) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class ToolExecutor:
    """Executes tool calls with validation."""

    def __init__(self, registry: ToolRegistry) -> None:
        """
        Initialize executor.

        Args:
            registry: Tool registry to look up tools
        """
        self.registry = registry

    async def execute(self, tool_call: ToolCall) -> ActionResult:
        """
        Execute a single tool call.

        Args:
            tool_call: Parsed tool call

        Returns:
            ActionResult with success/error and data
        """
        # Look up tool
        tool = self.registry.get(tool_call.tool_name)
        if not tool:
            return ActionResult(
                success=False,
                error=f"Tool not found: {tool_call.tool_name}",
            )

        # Validate arguments
        valid, error = tool.validate_args(tool_call.arguments)
        if not valid:
            return ActionResult(success=False, error=f"Invalid arguments: {error}")

        # Check if approval required
        if tool.requires_approval:
            logger.warning(
                f"Tool {tool.name} requires approval but approval workflow not implemented yet"
            )
            # For now, just execute anyway
            # TODO: Implement approval workflow in Phase 7

        # Execute tool
        try:
            logger.info(f"Executing tool: {tool_call.tool_name} with args: {tool_call.arguments}")
            result = await tool.executor(**tool_call.arguments)
            logger.debug(f"Tool {tool_call.tool_name} result: {_truncate_for_logging(result)}")
            return result
        except TypeError as e:
            # Argument mismatch
            return ActionResult(
                success=False,
                error=f"Tool execution failed: Invalid arguments - {e}",
            )
        except Exception as e:
            logger.error(f"Tool {tool_call.tool_name} failed: {e}", exc_info=True)
            return ActionResult(success=False, error=f"Tool execution failed: {e}")

    async def execute_all(self, tool_calls: list[ToolCall]) -> list[ActionResult]:
        """
        Execute multiple tool calls.

        Args:
            tool_calls: List of parsed tool calls

        Returns:
            List of action results (same order as input)
        """
        results = []
        for call in tool_calls:
            result = await self.execute(call)
            results.append(result)
        return results

    def format_results_for_llm(self, results: list[ActionResult]) -> str:
        """
        Format tool execution results for LLM consumption.

        Args:
            results: List of action results

        Returns:
            Formatted string for system message
        """
        if not results:
            return "No tools were executed."

        lines = ["# Tool Execution Results\n"]

        for i, result in enumerate(results, 1):
            if result.success:
                lines.append(f"Tool {i}: SUCCESS")
                if result.data:
                    # Format data as JSON (with datetime handling)
                    formatted = json.dumps(
                        result.data,
                        indent=2,
                        cls=DateTimeEncoder,
                    )
                    lines.append(f"Result: {formatted}")
            else:
                lines.append(f"Tool {i}: FAILED")
                lines.append(f"Error: {result.error}")
            lines.append("")  # Blank line

        return "\n".join(lines)
