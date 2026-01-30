"""Base tool definitions and decorators."""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from sentinel.core.types import ActionResult, RiskLevel
from sentinel.core.typing import ToolSpec


@dataclass
class ToolParameter:
    """Definition of a tool parameter."""

    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None


@dataclass
class Tool:
    """Definition of a callable tool."""

    name: str
    description: str
    parameters: list[ToolParameter]
    executor: Callable[..., Awaitable[ActionResult]]
    requires_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    examples: list[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Format tool for LLM context."""
        params_str = ", ".join(
            f"{p.name}: {p.type}" + ("" if p.required else " (optional)")
            for p in self.parameters
        )

        lines = [f"{self.name}({params_str})"]
        lines.append(f"  {self.description}")

        if self.parameters:
            lines.append("  Parameters:")
            for p in self.parameters:
                req = "required" if p.required else "optional"
                lines.append(f"    - {p.name} ({p.type}, {req}): {p.description}")
                if p.default is not None:
                    lines.append(f"      default: {p.default}")

        if self.examples:
            lines.append("  Examples:")
            for ex in self.examples:
                lines.append(f"    {ex}")

        return "\n".join(lines)

    def validate_args(self, args: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate tool arguments.

        Returns:
            (valid, error_message)
        """
        # Check required parameters
        required_params = {p.name for p in self.parameters if p.required}
        missing = required_params - set(args.keys())
        if missing:
            return False, f"Missing required parameters: {', '.join(missing)}"

        # Check unknown parameters
        valid_params = {p.name for p in self.parameters}
        unknown = set(args.keys()) - valid_params
        if unknown:
            return False, f"Unknown parameters: {', '.join(unknown)}"

        # Type validation could be added here
        return True, None

    def to_openai_function(self) -> ToolSpec:
        """
        Convert to OpenAI function calling format.

        Returns:
            Dict in OpenAI function format
        """
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def to_anthropic_tool(self) -> ToolSpec:
        """
        Convert to Anthropic tool use format.

        Returns:
            Dict in Anthropic tool format
        """
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }


F = TypeVar("F", bound=Callable[..., Awaitable[ActionResult]])


def tool(
    name: str,
    description: str,
    requires_approval: bool = False,
    risk_level: RiskLevel = RiskLevel.LOW,
    examples: list[str] | None = None,
) -> Callable[[F], F]:
    """
    Decorator to register a function as a tool.

    Args:
        name: Tool name (e.g., "add_reminder")
        description: Human-readable description
        requires_approval: Whether tool needs user approval before execution
        risk_level: Risk level (LOW, MEDIUM, HIGH, CRITICAL)
        examples: Example usage strings

    Example:
        @tool("add_reminder", "Set a one-time reminder")
        async def add_reminder(delay: str, message: str) -> ActionResult:
            pass
    """

    def decorator(func: F) -> F:
        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = []

        for param_name, param in sig.parameters.items():
            # Skip self/cls
            if param_name in ("self", "cls"):
                continue

            # Determine type from annotation
            param_type = "string"  # default
            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation
                # Handle common types
                if annotation in (str, "str"):
                    param_type = "string"
                elif annotation in (int, float, "int", "float"):
                    param_type = "number"
                elif annotation in (bool, "bool"):
                    param_type = "boolean"
                elif annotation in (dict, "dict"):
                    param_type = "object"
                elif annotation in (list, "list"):
                    param_type = "array"

            # Determine if required (has default value?)
            required = param.default == inspect.Parameter.empty
            default = None if required else param.default

            # Get description from docstring if available
            param_desc = f"Parameter {param_name}"
            if func.__doc__:
                # Try to extract param description from docstring
                # Simple parsing: look for "param_name: description"
                for line in func.__doc__.split("\n"):
                    if param_name in line and ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2 and param_name in parts[0]:
                            param_desc = parts[1].strip()
                            break

            parameters.append(
                ToolParameter(
                    name=param_name,
                    type=param_type,
                    description=param_desc,
                    required=required,
                    default=default,
                )
            )

        # Create Tool instance
        tool_instance = Tool(
            name=name,
            description=description,
            parameters=parameters,
            executor=func,
            requires_approval=requires_approval,
            risk_level=risk_level,
            examples=examples or [],
        )

        # Attach tool instance to function for registry discovery
        func._tool = tool_instance  # type: ignore

        return func

    return decorator
