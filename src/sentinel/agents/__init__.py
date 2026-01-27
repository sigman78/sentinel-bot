"""
Agents module - specialized AI agents.

Agents:
- base: Abstract agent interface
- dialog: Main conversation agent
- sleep: Background memory consolidation
- awareness: Proactive monitoring

Each agent has isolated context, accesses shared memory via defined interfaces.
"""

from sentinel.agents.awareness import AwarenessAgent
from sentinel.agents.base import AgentConfig, AgentState, BaseAgent
from sentinel.agents.dialog import DialogAgent
from sentinel.agents.sleep import SleepAgent

__all__ = [
    "AgentConfig",
    "AgentState",
    "AwarenessAgent",
    "BaseAgent",
    "DialogAgent",
    "SleepAgent",
]
