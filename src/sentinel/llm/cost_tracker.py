"""
Cost tracking and budget enforcement.

Tracks LLM API costs and enforces daily spending limits.
"""

from datetime import date, datetime


class CostTracker:
    """Track LLM API costs and enforce daily limits."""

    def __init__(self, daily_limit: float):
        """Initialize cost tracker.

        Args:
            daily_limit: Maximum daily spending in USD
        """
        self._daily_limit = daily_limit
        # Store costs as (timestamp, amount) tuples
        self._costs: list[tuple[datetime, float]] = []

    def add_cost(self, cost: float) -> None:
        """Record a cost.

        Args:
            cost: Cost in USD
        """
        self._costs.append((datetime.now(), cost))
        self._cleanup_old_costs()

    def _cleanup_old_costs(self) -> None:
        """Remove costs older than today."""
        today = date.today()
        self._costs = [(ts, cost) for ts, cost in self._costs if ts.date() == today]

    def get_today_total(self) -> float:
        """Get total cost for today.

        Returns:
            Total cost in USD
        """
        self._cleanup_old_costs()
        return sum(cost for _, cost in self._costs)

    def get_remaining_budget(self) -> float:
        """Get remaining budget for today.

        Returns:
            Remaining budget in USD (0 if over limit)
        """
        return max(0.0, self._daily_limit - self.get_today_total())

    def is_over_budget(self) -> bool:
        """Check if over daily limit.

        Returns:
            True if daily limit exceeded
        """
        return self.get_today_total() >= self._daily_limit

    def should_use_cheaper_model(self, threshold: float = 0.8) -> bool:
        """Check if approaching budget limit.

        Args:
            threshold: Budget threshold (0.0-1.0), default 80%

        Returns:
            True if current spending >= threshold * daily_limit
        """
        return self.get_today_total() >= (self._daily_limit * threshold)

    def get_cost_summary(self) -> dict[str, float]:
        """Get cost summary.

        Returns:
            Dict with today_total, daily_limit, remaining, percent_used
        """
        total = self.get_today_total()
        return {
            "today_total": total,
            "daily_limit": self._daily_limit,
            "remaining": self.get_remaining_budget(),
            "percent_used": (total / self._daily_limit * 100) if self._daily_limit > 0 else 0,
        }
