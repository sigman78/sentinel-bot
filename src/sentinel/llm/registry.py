"""
Model capability registry.

Centralized registry of all available models with cost, performance, and capability metadata.
"""

from dataclasses import dataclass

from sentinel.llm.base import ProviderType


@dataclass
class ModelCapability:
    """Model capability and cost information."""

    model_id: str
    provider: ProviderType
    difficulty: int  # 1=Easy, 2=Intermediate, 3=Hard
    cost_per_1m_input: float  # USD per 1M input tokens
    cost_per_1m_output: float  # USD per 1M output tokens
    max_context: int  # Maximum context window in tokens
    avg_latency_ms: int  # Estimated average latency
    quality_score: float  # 0.0-1.0 subjective quality rating
    multimodal: bool = False  # Supports image/audio input
    supports_tools: bool = True  # Supports function calling
    notes: str = ""  # Additional notes


# Registry of all available models
MODEL_REGISTRY: dict[str, ModelCapability] = {
    # === Claude Models (Anthropic) ===
    # Hard difficulty (3) - Complex reasoning
    "claude-opus-4-20250514": ModelCapability(
        model_id="claude-opus-4-20250514",
        provider=ProviderType.CLAUDE,
        difficulty=3,
        cost_per_1m_input=15.0,
        cost_per_1m_output=75.0,
        max_context=200_000,
        avg_latency_ms=3000,
        quality_score=1.0,
        multimodal=True,
        notes="Best reasoning, highest cost",
    ),
    "claude-sonnet-4-20250514": ModelCapability(
        model_id="claude-sonnet-4-20250514",
        provider=ProviderType.CLAUDE,
        difficulty=3,
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        max_context=200_000,
        avg_latency_ms=2000,
        quality_score=0.95,
        multimodal=True,
        notes="Balanced quality/cost for complex tasks",
    ),
    # Intermediate difficulty (2)
    "claude-haiku-3-5-20241022": ModelCapability(
        model_id="claude-haiku-3-5-20241022",
        provider=ProviderType.CLAUDE,
        difficulty=2,
        cost_per_1m_input=0.8,
        cost_per_1m_output=4.0,
        max_context=200_000,
        avg_latency_ms=800,
        quality_score=0.85,
        multimodal=True,
        notes="Fast, cheap, good for simple tasks",
    ),
    # === OpenRouter Models ===
    # Hard difficulty (3)
    "anthropic/claude-3.5-sonnet": ModelCapability(
        model_id="anthropic/claude-3.5-sonnet",
        provider=ProviderType.OPENROUTER,
        difficulty=3,
        cost_per_1m_input=3.0,
        cost_per_1m_output=15.0,
        max_context=200_000,
        avg_latency_ms=2500,
        quality_score=0.95,
        multimodal=True,
    ),
    "openai/gpt-4-turbo": ModelCapability(
        model_id="openai/gpt-4-turbo",
        provider=ProviderType.OPENROUTER,
        difficulty=3,
        cost_per_1m_input=10.0,
        cost_per_1m_output=30.0,
        max_context=128_000,
        avg_latency_ms=2500,
        quality_score=0.92,
        multimodal=True,
    ),
    # Intermediate difficulty (2)
    "google/gemini-pro-1.5": ModelCapability(
        model_id="google/gemini-pro-1.5",
        provider=ProviderType.OPENROUTER,
        difficulty=2,
        cost_per_1m_input=1.25,
        cost_per_1m_output=5.0,
        max_context=1_000_000,
        avg_latency_ms=2000,
        quality_score=0.85,
        multimodal=True,
        notes="Huge context window",
    ),
    "anthropic/claude-3-haiku": ModelCapability(
        model_id="anthropic/claude-3-haiku",
        provider=ProviderType.OPENROUTER,
        difficulty=2,
        cost_per_1m_input=0.25,
        cost_per_1m_output=1.25,
        max_context=200_000,
        avg_latency_ms=1000,
        quality_score=0.8,
        multimodal=True,
    ),
    "meta-llama/llama-3.1-70b-instruct": ModelCapability(
        model_id="meta-llama/llama-3.1-70b-instruct",
        provider=ProviderType.OPENROUTER,
        difficulty=2,
        cost_per_1m_input=0.52,
        cost_per_1m_output=0.75,
        max_context=128_000,
        avg_latency_ms=1500,
        quality_score=0.75,
    ),
    # Easy difficulty (1)
    "openai/gpt-4o-mini": ModelCapability(
        model_id="openai/gpt-4o-mini",
        provider=ProviderType.OPENROUTER,
        difficulty=1,
        cost_per_1m_input=0.15,
        cost_per_1m_output=0.6,
        max_context=128_000,
        avg_latency_ms=1000,
        quality_score=0.75,
        multimodal=True,
    ),
    "google/gemini-flash-1.5": ModelCapability(
        model_id="google/gemini-flash-1.5",
        provider=ProviderType.OPENROUTER,
        difficulty=1,
        cost_per_1m_input=0.075,
        cost_per_1m_output=0.3,
        max_context=1_000_000,
        avg_latency_ms=800,
        quality_score=0.7,
        multimodal=True,
        notes="Very fast, huge context",
    ),
    "meta-llama/llama-3.1-8b-instruct": ModelCapability(
        model_id="meta-llama/llama-3.1-8b-instruct",
        provider=ProviderType.OPENROUTER,
        difficulty=1,
        cost_per_1m_input=0.05,
        cost_per_1m_output=0.08,
        max_context=128_000,
        avg_latency_ms=600,
        quality_score=0.65,
    ),
    "qwen/qwen-2.5-72b-instruct": ModelCapability(
        model_id="qwen/qwen-2.5-72b-instruct",
        provider=ProviderType.OPENROUTER,
        difficulty=1,
        cost_per_1m_input=0.35,
        cost_per_1m_output=0.4,
        max_context=32_768,
        avg_latency_ms=1200,
        quality_score=0.7,
    ),
    # === Local Models (placeholder) ===
    "local": ModelCapability(
        model_id="local",
        provider=ProviderType.LOCAL,
        difficulty=1,
        cost_per_1m_input=0.0,
        cost_per_1m_output=0.0,
        max_context=32_768,
        avg_latency_ms=2000,
        quality_score=0.6,
        notes="Free local inference, variable quality",
    ),
}


def get_model_info(model_id: str) -> ModelCapability | None:
    """Get model capability information by model ID.

    Args:
        model_id: The model identifier

    Returns:
        ModelCapability if found, None otherwise
    """
    return MODEL_REGISTRY.get(model_id)


def get_models_by_difficulty(
    difficulty: int, provider: ProviderType | None = None
) -> list[ModelCapability]:
    """Get all models matching difficulty level, optionally filtered by provider.

    Args:
        difficulty: Difficulty level (1=Easy, 2=Intermediate, 3=Hard)
        provider: Optional provider filter

    Returns:
        List of matching model capabilities
    """
    models = [m for m in MODEL_REGISTRY.values() if m.difficulty == difficulty]
    if provider:
        models = [m for m in models if m.provider == provider]
    return models


def rank_models_by_cost(models: list[ModelCapability]) -> list[ModelCapability]:
    """Sort models by total cost (input + output), cheapest first.

    Args:
        models: List of model capabilities

    Returns:
        Sorted list (cheapest to most expensive)
    """
    return sorted(
        models, key=lambda m: m.cost_per_1m_input + m.cost_per_1m_output
    )


def filter_by_capabilities(
    models: list[ModelCapability],
    multimodal: bool = False,
    min_context: int = 0,
) -> list[ModelCapability]:
    """Filter models by capability requirements.

    Args:
        models: List of model capabilities
        multimodal: Require multimodal support
        min_context: Minimum context window size

    Returns:
        Filtered list of models
    """
    filtered = models
    if multimodal:
        filtered = [m for m in filtered if m.multimodal]
    if min_context > 0:
        filtered = [m for m in filtered if m.max_context >= min_context]
    return filtered
