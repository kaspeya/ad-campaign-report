import argparse

import pandas as pd
import pytest

from ad_report.periods import month_range, parse_month, period_bounds, reference_date


@pytest.mark.parametrize("s, expected", [
    ("01.2024", (2024, 1)),
    ("12.2025", (2025, 12)),
    ("03.2026", (2026, 3)),
])
def test_parse_month_valid(s, expected) -> None:
    assert parse_month(s) == expected


@pytest.mark.parametrize("s", ["13.2024", "1.2024", "2024.01", "00.2024"])
def test_parse_month_invalid(s) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_month(s)


def test_reference_date_is_last_day_of_month() -> None:
    assert reference_date(2024, 2) == pd.Timestamp(2024, 2, 29)
    assert reference_date(2025, 2) == pd.Timestamp(2025, 2, 28)
    assert reference_date(2025, 12) == pd.Timestamp(2025, 12, 31)


def test_period_bounds() -> None:
    start, end = period_bounds((2024, 1), (2025, 6))
    assert start == pd.Timestamp(2024, 1, 1)
    assert end == pd.Timestamp(2025, 6, 30)


def test_month_range_crosses_year_boundary() -> None:
    assert month_range((2024, 11), (2025, 2)) == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]
    assert month_range((2024, 5), (2024, 5)) == [(2024, 5)]
