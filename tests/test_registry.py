"""Tests for model registry."""

from sentinel.llm.base import ProviderType
from sentinel.llm.registry import (
    MODEL_REGISTRY,
    filter_by_capabilities,
    get_model_info,
    get_models_by_difficulty,
    rank_models_by_cost,
)


def test_get_model_info_exists():
    """Can retrieve model info from registry."""
    info = get_model_info("claude-sonnet-4-20250514")
    assert info is not None
    assert info.model_id == "claude-sonnet-4-20250514"
    assert info.provider == ProviderType.CLAUDE
    assert info.difficulty == 3
    assert info.cost_per_1m_input == 3.0
    assert info.cost_per_1m_output == 15.0


def test_get_model_info_not_exists():
    """Returns None for unknown model."""
    info = get_model_info("nonexistent-model")
    assert info is None


def test_get_models_by_difficulty_hard():
    """Can filter hard difficulty models."""
    hard = get_models_by_difficulty(3)
    assert len(hard) > 0
    assert all(m.difficulty == 3 for m in hard)
    # Should include opus and sonnet
    model_ids = [m.model_id for m in hard]
    assert "claude-opus-4-20250514" in model_ids
    assert "claude-sonnet-4-20250514" in model_ids


def test_get_models_by_difficulty_intermediate():
    """Can filter intermediate difficulty models."""
    intermediate = get_models_by_difficulty(2)
    assert len(intermediate) > 0
    assert all(m.difficulty == 2 for m in intermediate)


def test_get_models_by_difficulty_easy():
    """Can filter easy difficulty models."""
    easy = get_models_by_difficulty(1)
    assert len(easy) > 0
    assert all(m.difficulty == 1 for m in easy)


def test_get_models_by_difficulty_and_provider():
    """Can filter by both difficulty and provider."""
    claude_hard = get_models_by_difficulty(3, provider=ProviderType.CLAUDE)
    assert len(claude_hard) > 0
    assert all(m.difficulty == 3 and m.provider == ProviderType.CLAUDE for m in claude_hard)

    openrouter_easy = get_models_by_difficulty(1, provider=ProviderType.OPENROUTER)
    assert len(openrouter_easy) > 0
    assert all(m.difficulty == 1 and m.provider == ProviderType.OPENROUTER for m in openrouter_easy)


def test_rank_models_by_cost():
    """Models sorted by total cost (input + output)."""
    models = get_models_by_difficulty(1)
    ranked = rank_models_by_cost(models)

    # Check ordering: each model should be <= next in total cost
    for i in range(len(ranked) - 1):
        current_cost = ranked[i].cost_per_1m_input + ranked[i].cost_per_1m_output
        next_cost = ranked[i + 1].cost_per_1m_input + ranked[i + 1].cost_per_1m_output
        assert current_cost <= next_cost


def test_filter_by_multimodal():
    """Can filter models requiring multimodal support."""
    all_models = list(MODEL_REGISTRY.values())
    multimodal = filter_by_capabilities(all_models, multimodal=True)

    assert len(multimodal) > 0
    assert all(m.multimodal for m in multimodal)


def test_filter_by_min_context():
    """Can filter models by minimum context window."""
    all_models = list(MODEL_REGISTRY.values())
    large_context = filter_by_capabilities(all_models, min_context=100_000)

    assert len(large_context) > 0
    assert all(m.max_context >= 100_000 for m in large_context)


def test_registry_completeness():
    """All registry entries have required fields."""
    for model_id, model_cap in MODEL_REGISTRY.items():
        assert model_cap.model_id == model_id
        assert model_cap.provider in [ProviderType.CLAUDE, ProviderType.OPENROUTER, ProviderType.LOCAL]
        assert model_cap.difficulty in [1, 2, 3]
        assert model_cap.cost_per_1m_input >= 0
        assert model_cap.cost_per_1m_output >= 0
        assert model_cap.max_context > 0
        assert model_cap.avg_latency_ms > 0
        assert 0.0 <= model_cap.quality_score <= 1.0


def test_all_difficulty_levels_have_models():
    """Registry contains models for each difficulty level."""
    assert len(get_models_by_difficulty(1)) > 0  # Easy
    assert len(get_models_by_difficulty(2)) > 0  # Intermediate
    assert len(get_models_by_difficulty(3)) > 0  # Hard


def test_local_model_zero_cost():
    """Local models have zero cost."""
    local_info = get_model_info("local")
    assert local_info is not None
    assert local_info.cost_per_1m_input == 0.0
    assert local_info.cost_per_1m_output == 0.0
    assert local_info.provider == ProviderType.LOCAL
