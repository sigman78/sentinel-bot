"""
Core module - orchestration, configuration, shared types.

Components:
- config: Settings management via pydantic-settings
- types: Shared data structures (Message, Action, etc.)
- orchestrator: Central agent coordinator
- logging: Structured logging setup
"""

from sentinel.core.config import Settings
from sentinel.core.types import ContentType, Message

__all__ = ["Settings", "Message", "ContentType"]
