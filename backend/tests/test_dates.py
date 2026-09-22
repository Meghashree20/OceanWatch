from datetime import datetime, timezone

import pytest

from app.core.dates import parse_date_bound, parse_date_range


def test_date_only_end_is_inclusive_end_of_day():
    value = parse_date_bound("2024-12-31", end_of_day=True)
    assert value == datetime(2024, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_same_date_range_is_inclusive():
    start, end = parse_date_range("2024-01-01", "2024-01-01")
    assert start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert end.hour == 23


def test_datetime_input_is_normalized_to_utc():
    start, end = parse_date_range("2024-01-01T05:00:00-05:00", "2024-01-02T00:00:00Z")
    assert start == datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
    assert end == datetime(2024, 1, 2, tzinfo=timezone.utc)


def test_invalid_date_format_is_rejected():
    with pytest.raises(ValueError, match="Invalid ISO"):
        parse_date_bound("not-a-date")


def test_end_before_start_is_rejected():
    with pytest.raises(ValueError, match="end_date"):
        parse_date_range("2024-02-01", "2024-01-31")


def test_empty_range_is_valid_and_returns_no_bounds():
    assert parse_date_range(None, None) == (None, None)