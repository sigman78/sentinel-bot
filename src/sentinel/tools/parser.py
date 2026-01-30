"""Parse tool calls from LLM responses."""

import json
import re
from dataclasses import dataclass
from typing import Any

from sentinel.core.logging import get_logger

logger = get_logger("tools.parser")


@dataclass
class ToolCall:
    """A parsed tool call from LLM output."""

    tool_name: str
    arguments: dict[str, Any]
    raw_json: str


class ToolParser:
    """Extract and parse tool calls from LLM text."""

    @staticmethod
    def extract_calls(text: str) -> list[ToolCall]:
        """
        Extract tool calls from LLM response.

        Looks for JSON blocks in various formats:
        - ```json ... ```
        - ``` ... ```
        - Raw JSON objects {...}

        Args:
            text: LLM response text

        Returns:
            List of parsed tool calls
        """
        calls = []

        # Strategy 1: Extract from ```json code blocks
        json_blocks = re.findall(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        for block in json_blocks:
            tool_call = ToolParser._parse_json_block(block)
            if tool_call:
                calls.append(tool_call)

        # Strategy 2: Extract from ``` code blocks (no language specified)
        if not calls:
            code_blocks = re.findall(r"```\s*\n(.*?)\n```", text, re.DOTALL)
            for block in code_blocks:
                # Skip if looks like non-JSON code
                if block.strip().startswith(("{", "[")):
                    tool_call = ToolParser._parse_json_block(block)
                    if tool_call:
                        calls.append(tool_call)

        # Strategy 3: Find raw JSON objects (with or without newlines)
        if not calls:
            # Look for {...} patterns that might be tool calls
            # More permissive pattern to match nested JSON
            json_patterns = re.findall(
                r'\{(?:[^{}]|\{[^{}]*\})*?"tool"\s*:\s*"[^"]*"(?:[^{}]|\{[^{}]*\})*?\}',
                text,
                re.DOTALL,
            )
            for pattern in json_patterns:
                tool_call = ToolParser._parse_json_block(pattern)
                if tool_call:
                    calls.append(tool_call)

        return calls

    @staticmethod
    def _parse_json_block(block: str) -> ToolCall | None:
        """
        Parse a JSON block into a ToolCall.

        Args:
            block: JSON string

        Returns:
            ToolCall or None if parsing fails
        """
        try:
            data = json.loads(block.strip())

            # Validate structure
            if not isinstance(data, dict):
                return None

            if "tool" not in data:
                return None

            tool_name = data["tool"]
            arguments = data.get("args", {})

            if not isinstance(arguments, dict):
                logger.warning(f"Tool call has invalid args type: {type(arguments)}")
                return None

            return ToolCall(tool_name=tool_name, arguments=arguments, raw_json=block.strip())

        except json.JSONDecodeError as e:
            logger.debug(f"Failed to parse JSON block: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error parsing tool call: {e}")
            return None
