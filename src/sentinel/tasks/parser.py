"""Parse time delays and schedule patterns."""

import re
from datetime import datetime, timedelta


class ScheduleParser:
    """Parse schedule expressions into structured data."""

    @staticmethod
    def parse_delay(text: str) -> timedelta:
        """
        Parse time delay expressions.

        Supported formats:
        - "5m" or "5 minutes" → 5 minutes
        - "2h" or "2 hours" → 2 hours
        - "1d" or "1 day" → 1 day
        - "30s" or "30 seconds" → 30 seconds

        Raises:
            ValueError: If format is invalid
        """
        text = text.strip().lower()

        # Pattern: number + unit
        pattern = r"^(\d+)\s*([smhd]|sec|min|hour|day|seconds?|minutes?|hours?|days?)s?$"
        match = re.match(pattern, text)

        if not match:
            raise ValueError(f"Invalid delay format: {text}")

        amount = int(match.group(1))
        unit = match.group(2)

        # Map units to timedelta
        if unit in ("s", "sec", "second", "seconds"):
            return timedelta(seconds=amount)
        elif unit in ("m", "min", "minute", "minutes"):
            return timedelta(minutes=amount)
        elif unit in ("h", "hour", "hours"):
            return timedelta(hours=amount)
        elif unit in ("d", "day", "days"):
            return timedelta(days=amount)
        else:
            raise ValueError(f"Unknown time unit: {unit}")

    @staticmethod
    def parse_recurring(text: str) -> dict:
        """
        Parse recurring schedule patterns.

        Supported formats:
        - "daily 9am" or "daily 09:00" → Run every day at 9am
        - "weekdays 6pm" or "weekdays 18:00" → Run Mon-Fri at 6pm
        - "monday 10am" → Run every Monday at 10am

        Returns dict with pattern and time.

        Raises:
            ValueError: If format is invalid
        """
        text = text.strip().lower()

        # Parse "daily HH:MM" or "daily HHam/pm"
        daily_pattern = r"^daily\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$"
        match = re.match(daily_pattern, text)
        if match:
            hour, minute, meridiem = match.groups()
            time_str = ScheduleParser._parse_time(hour, minute or "00", meridiem)
            return {"pattern": "daily", "time": time_str}

        # Parse "weekdays HH:MM" or "weekdays HHam/pm"
        weekdays_pattern = r"^weekdays\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$"
        match = re.match(weekdays_pattern, text)
        if match:
            hour, minute, meridiem = match.groups()
            time_str = ScheduleParser._parse_time(hour, minute or "00", meridiem)
            return {"pattern": "weekdays", "time": time_str}

        # Parse "monday/tuesday/etc 10am"
        day_pattern = r"^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(\d{1,2}):?(\d{2})?\s*(am|pm)?$"
        match = re.match(day_pattern, text)
        if match:
            day, hour, minute, meridiem = match.groups()
            time_str = ScheduleParser._parse_time(hour, minute or "00", meridiem)
            return {"pattern": day, "time": time_str}

        raise ValueError(f"Invalid recurring pattern: {text}")

    @staticmethod
    def _parse_time(hour: str, minute: str, meridiem: str | None) -> str:
        """Convert hour/minute/meridiem to HH:MM 24-hour format."""
        h = int(hour)
        m = int(minute)

        if meridiem:
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0

        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError(f"Invalid time: {hour}:{minute} {meridiem}")

        return f"{h:02d}:{m:02d}"

    @staticmethod
    def calculate_next_run(schedule_data: dict, after: datetime) -> datetime:
        """
        Calculate next run time from schedule_data.

        Args:
            schedule_data: Dict with 'pattern' and 'time' keys
            after: Calculate next run after this datetime

        Returns:
            Next scheduled datetime
        """
        pattern = schedule_data["pattern"]
        time_str = schedule_data["time"]  # "HH:MM" format

        # Parse time
        hour, minute = map(int, time_str.split(":"))

        if pattern == "daily":
            # Next occurrence today or tomorrow
            next_run = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= after:
                next_run += timedelta(days=1)
            return next_run

        elif pattern == "weekdays":
            # Next weekday (Mon-Fri)
            next_run = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= after:
                next_run += timedelta(days=1)

            # Skip to next weekday
            while next_run.weekday() >= 5:  # 5=Saturday, 6=Sunday
                next_run += timedelta(days=1)
            return next_run

        elif pattern in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            # Specific day of week
            day_map = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            target_day = day_map[pattern]

            next_run = after.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= after:
                next_run += timedelta(days=1)

            # Advance to target weekday
            while next_run.weekday() != target_day:
                next_run += timedelta(days=1)
            return next_run

        else:
            raise ValueError(f"Unknown schedule pattern: {pattern}")
