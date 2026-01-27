"""Tests for cost tracking."""

from sentinel.llm.cost_tracker import CostTracker


def test_cost_tracker_init():
    """CostTracker initializes with daily limit."""
    tracker = CostTracker(daily_limit=5.0)
    assert tracker._daily_limit == 5.0
    assert tracker.get_today_total() == 0.0


def test_add_cost():
    """Can add costs to tracker."""
    tracker = CostTracker(daily_limit=10.0)
    tracker.add_cost(1.5)
    tracker.add_cost(2.3)
    assert tracker.get_today_total() == 3.8


def test_remaining_budget():
    """Remaining budget calculated correctly."""
    tracker = CostTracker(daily_limit=10.0)
    tracker.add_cost(3.0)
    assert tracker.get_remaining_budget() == 7.0


def test_over_budget():
    """Detects when over budget."""
    tracker = CostTracker(daily_limit=5.0)
    tracker.add_cost(3.0)
    assert not tracker.is_over_budget()

    tracker.add_cost(2.5)
    assert tracker.is_over_budget()


def test_should_use_cheaper_model_default_threshold():
    """Cheaper model suggested at 80% threshold."""
    tracker = CostTracker(daily_limit=10.0)
    tracker.add_cost(7.5)  # 75%
    assert not tracker.should_use_cheaper_model()

    tracker.add_cost(0.6)  # 81%
    assert tracker.should_use_cheaper_model()


def test_should_use_cheaper_model_custom_threshold():
    """Can specify custom threshold."""
    tracker = CostTracker(daily_limit=10.0)
    tracker.add_cost(5.5)  # 55%

    assert not tracker.should_use_cheaper_model(threshold=0.6)
    assert tracker.should_use_cheaper_model(threshold=0.5)


def test_get_cost_summary():
    """Cost summary includes all metrics."""
    tracker = CostTracker(daily_limit=20.0)
    tracker.add_cost(12.0)

    summary = tracker.get_cost_summary()
    assert summary["today_total"] == 12.0
    assert summary["daily_limit"] == 20.0
    assert summary["remaining"] == 8.0
    assert summary["percent_used"] == 60.0


def test_zero_budget_edge_case():
    """Handles zero budget gracefully."""
    tracker = CostTracker(daily_limit=0.0)
    tracker.add_cost(0.1)

    assert tracker.is_over_budget()
    summary = tracker.get_cost_summary()
    assert summary["percent_used"] == 0  # Avoid division by zero
