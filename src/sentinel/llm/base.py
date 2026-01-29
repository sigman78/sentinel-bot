"""Base LLM types and interfaces."""

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMConfig:
    """LLM request configuration."""

    model: str | None  # Specific model override (None = use router default)
    max_tokens: int = 4096
    temperature: float = 0.7
    system_prompt: str | None = None


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    model: str
    provider: str  # Provider name (e.g., 'anthropic', 'openrouter', 'ollama')
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    tool_calls: list[dict[str, Any]] | None = None
    metadata: dict | None = None
