"""System utility tools."""

from datetime import datetime

from sentinel.core.types import ActionResult
from sentinel.tools.base import tool
from sentinel.tools.registry import register_tool


@tool(
    "get_current_time",
    "Get the current date and time",
    examples=["get_current_time()"],
)
async def get_current_time() -> ActionResult:
    """
    Get current date and time.

    Returns:
        ActionResult with current datetime information
    """
    now = datetime.now()
    return ActionResult(
        success=True,
        data={
            "datetime": now.isoformat(),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": now.astimezone().tzname(),
        },
    )


def register_system_tools() -> None:
    """Register system tools with the global registry."""
    register_tool(get_current_time._tool)  # type: ignore[attr-defined]
