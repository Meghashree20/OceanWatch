"""Shared UTC date parsing and inclusive date-range handling."""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional


UTC = timezone.utc


def parse_date_bound(value: Optional[str | datetime | date], *, end_of_day: bool = False) -> Optional[datetime]:
    """Parse ISO date/datetime input into a UTC-aware inclusive query bound.

    Naive datetimes are interpreted as UTC. Date-only end bounds become the last
    microsecond of that UTC calendar day.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
        date_only = False
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
        date_only = True
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError("Date value must not be empty")
        date_only = len(text) == 10
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"Invalid ISO date/datetime: {value}") from exc
    else:
        raise ValueError("Date value must be ISO date or datetime")

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    else:
        parsed = parsed.astimezone(UTC)
    if end_of_day and date_only:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


def parse_date_range(start_date: Optional[str | datetime], end_date: Optional[str | datetime]) -> tuple[Optional[datetime], Optional[datetime]]:
    start = parse_date_bound(start_date)
    end = parse_date_bound(end_date, end_of_day=True)
    if start and end and end < start:
        raise ValueError("end_date must be greater than or equal to start_date")
    return start, end
