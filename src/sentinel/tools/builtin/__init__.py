"""Built-in tools."""

from sentinel.tools.builtin.agenda import register_agenda_tools
from sentinel.tools.builtin.delegation import register_delegation_tools
from sentinel.tools.builtin.system import register_system_tools
from sentinel.tools.builtin.tasks import register_task_tools
from sentinel.tools.builtin.web_search import register_web_search_tools


def register_all_builtin_tools() -> None:
    """Register all built-in tools with the global registry."""
    register_task_tools()
    register_system_tools()
    register_agenda_tools()
    register_delegation_tools()
    register_web_search_tools()


__all__ = ["register_all_builtin_tools"]
