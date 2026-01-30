"""Tests for YAML-based model registry."""

from sentinel.llm.litellm_adapter import create_adapter


def test_registry_loads_from_yaml():
    """Registry successfully loads models from YAML config."""
    adapter = create_adapter()
    registry = adapter.registry

    assert len(registry.models) > 0
    assert "claude-sonnet-4" in registry.models


def test_model_config_has_required_fields():
    """All models have required configuration fields."""
    adapter = create_adapter()
    registry = adapter.registry

    for model_id, model_config in registry.models.items():
        assert model_config.model_id == model_id
        assert model_config.litellm_name
        assert model_config.provider
        assert model_config.difficulty in [1, 2, 3]
        assert model_config.cost_per_1m_input >= 0
        assert model_config.cost_per_1m_output >= 0
        assert model_config.max_context > 0


def test_get_model_by_id():
    """Can retrieve model by ID."""
    adapter = create_adapter()
    registry = adapter.registry

    model = registry.get("claude-sonnet-4")
    assert model is not None
    assert model.model_id == "claude-sonnet-4"
    assert model.difficulty == 3


def test_get_nonexistent_model():
    """Returns None for unknown model ID."""
    adapter = create_adapter()
    registry = adapter.registry

    model = registry.get("nonexistent-model-xyz")
    assert model is None


def test_get_by_difficulty():
    """Can filter models by difficulty level."""
    adapter = create_adapter()
    registry = adapter.registry

    easy = registry.get_by_difficulty(1)
    intermediate = registry.get_by_difficulty(2)
    hard = registry.get_by_difficulty(3)

    # Should have models at each difficulty level
    assert len(hard) > 0
    assert all(m.difficulty == 3 for m in hard)

    if len(easy) > 0:
        assert all(m.difficulty == 1 for m in easy)

    if len(intermediate) > 0:
        assert all(m.difficulty == 2 for m in intermediate)


def test_rank_by_cost():
    """Models sorted by total cost (input + output)."""
    adapter = create_adapter()
    registry = adapter.registry

    # Get all models and rank
    all_models = list(registry.models.values())
    ranked = registry.rank_by_cost(all_models)

    # Check ordering: each model should be <= next in total cost
    for i in range(len(ranked) - 1):
        current_cost = ranked[i].cost_per_1m_input + ranked[i].cost_per_1m_output
        next_cost = ranked[i + 1].cost_per_1m_input + ranked[i + 1].cost_per_1m_output
        assert current_cost <= next_cost


def test_model_availability():
    """Model availability depends on credentials."""
    adapter = create_adapter()
    registry = adapter.registry

    # All models should have is_available property
    for model_config in registry.models.values():
        assert hasattr(model_config, "is_available")
        assert isinstance(model_config.is_available, bool)


def test_routing_config_loaded():
    """Registry loads routing configuration."""
    adapter = create_adapter()
    registry = adapter.registry

    assert hasattr(registry, "routing_config")
    assert isinstance(registry.routing_config, dict)


def test_multimodal_capability():
    """Some models support multimodal input."""
    adapter = create_adapter()
    registry = adapter.registry

    # Should have at least one multimodal model
    multimodal_models = [m for m in registry.models.values() if m.multimodal]
    assert len(multimodal_models) > 0


def test_local_model_zero_cost():
    """Local models have zero cost."""
    adapter = create_adapter()
    registry = adapter.registry

    local_models = [m for m in registry.models.values() if m.provider == "local"]

    for model in local_models:
        assert model.cost_per_1m_input == 0.0
        assert model.cost_per_1m_output == 0.0
