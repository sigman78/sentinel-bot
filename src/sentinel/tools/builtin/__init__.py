"""Built-in tools."""

from sentinel.tools.builtin.system import register_system_tools
from sentinel.tools.builtin.tasks import register_task_tools


def register_all_builtin_tools() -> None:
    """Register all built-in tools with the global registry."""
    register_task_tools()
    register_system_tools()


__all__ = ["register_all_builtin_tools"]
