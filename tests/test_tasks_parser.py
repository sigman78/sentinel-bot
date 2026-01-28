"""Tests for task schedule parser."""

from datetime import datetime, timedelta

import pytest

from sentinel.tasks.parser import ScheduleParser


class TestParseDelay:
    """Test delay parsing."""

    def test_parse_minutes(self):
        assert ScheduleParser.parse_delay("5m") == timedelta(minutes=5)
        assert ScheduleParser.parse_delay("5 minutes") == timedelta(minutes=5)
        assert ScheduleParser.parse_delay("1 minute") == timedelta(minutes=1)

    def test_parse_hours(self):
        assert ScheduleParser.parse_delay("2h") == timedelta(hours=2)
        assert ScheduleParser.parse_delay("2 hours") == timedelta(hours=2)
        assert ScheduleParser.parse_delay("1 hour") == timedelta(hours=1)

    def test_parse_days(self):
        assert ScheduleParser.parse_delay("1d") == timedelta(days=1)
        assert ScheduleParser.parse_delay("3 days") == timedelta(days=3)
        assert ScheduleParser.parse_delay("1 day") == timedelta(days=1)

    def test_parse_seconds(self):
        assert ScheduleParser.parse_delay("30s") == timedelta(seconds=30)
        assert ScheduleParser.parse_delay("30 seconds") == timedelta(seconds=30)
        assert ScheduleParser.parse_delay("1 second") == timedelta(seconds=1)

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid delay format"):
            ScheduleParser.parse_delay("invalid")

        with pytest.raises(ValueError, match="Invalid delay format"):
            ScheduleParser.parse_delay("5x")


class TestParseRecurring:
    """Test recurring pattern parsing."""

    def test_daily_pattern(self):
        result = ScheduleParser.parse_recurring("daily 9am")
        assert result == {"pattern": "daily", "time": "09:00"}

        result = ScheduleParser.parse_recurring("daily 14:30")
        assert result == {"pattern": "daily", "time": "14:30"}

        result = ScheduleParser.parse_recurring("daily 5pm")
        assert result == {"pattern": "daily", "time": "17:00"}

    def test_weekdays_pattern(self):
        result = ScheduleParser.parse_recurring("weekdays 9am")
        assert result == {"pattern": "weekdays", "time": "09:00"}

        result = ScheduleParser.parse_recurring("weekdays 18:00")
        assert result == {"pattern": "weekdays", "time": "18:00"}

    def test_specific_day_pattern(self):
        result = ScheduleParser.parse_recurring("monday 10am")
        assert result == {"pattern": "monday", "time": "10:00"}

        result = ScheduleParser.parse_recurring("friday 5pm")
        assert result == {"pattern": "friday", "time": "17:00"}

    def test_invalid_pattern(self):
        with pytest.raises(ValueError, match="Invalid recurring pattern"):
            ScheduleParser.parse_recurring("invalid pattern")


class TestCalculateNextRun:
    """Test next run calculation."""

    def test_daily_pattern_future(self):
        """Test daily pattern when time is in future today."""
        schedule_data = {"pattern": "daily", "time": "15:00"}
        after = datetime(2026, 1, 27, 10, 0)  # 10am

        next_run = ScheduleParser.calculate_next_run(schedule_data, after)

        # Should be today at 3pm
        assert next_run.year == 2026
        assert next_run.month == 1
        assert next_run.day == 27
        assert next_run.hour == 15
        assert next_run.minute == 0

    def test_daily_pattern_past(self):
        """Test daily pattern when time has passed today."""
        schedule_data = {"pattern": "daily", "time": "09:00"}
        after = datetime(2026, 1, 27, 10, 0)  # 10am

        next_run = ScheduleParser.calculate_next_run(schedule_data, after)

        # Should be tomorrow at 9am
        assert next_run.year == 2026
        assert next_run.month == 1
        assert next_run.day == 28
        assert next_run.hour == 9
        assert next_run.minute == 0

    def test_weekdays_pattern(self):
        """Test weekdays pattern skips weekend."""
        schedule_data = {"pattern": "weekdays", "time": "09:00"}
        # Friday 10am
        after = datetime(2026, 1, 23, 10, 0)

        next_run = ScheduleParser.calculate_next_run(schedule_data, after)

        # Should skip to Monday
        assert next_run.weekday() == 0  # Monday
        assert next_run.hour == 9

    def test_monday_pattern(self):
        """Test specific day pattern."""
        schedule_data = {"pattern": "monday", "time": "10:00"}
        # Wednesday
        after = datetime(2026, 1, 28, 10, 0)

        next_run = ScheduleParser.calculate_next_run(schedule_data, after)

        # Should be next Monday
        assert next_run.weekday() == 0  # Monday
        assert next_run.hour == 10
