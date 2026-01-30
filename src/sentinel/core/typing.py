"""Shared typing aliases used across modules."""

from typing import Any, TypeAlias

JSONDict: TypeAlias = dict[str, Any]
MessageDict: TypeAlias = dict[str, Any]
StringDict: TypeAlias = dict[str, str]
ToolCallDict: TypeAlias = dict[str, Any]
ToolSpec: TypeAlias = dict[str, Any]
