import argparse
from dataclasses import FrozenInstanceError

import pandas as pd
import pytest

from ad_report.audience import Audience, full_years, parse_audience, select_audience


@pytest.mark.parametrize("expr, expected", [
    ("ALL_18_35", Audience("ALL", 18, 35, frozenset())),
    ("W_25_45_BC", Audience("W", 25, 45, frozenset({"B", "C"}))),
    ("M_60+_A", Audience("M", 60, None, frozenset({"A"}))),
    ("M_25_40_B", Audience("M", 25, 40, frozenset({"B"}))),
])
def test_parse_audience_valid(expr, expected) -> None:
    assert parse_audience(expr) == expected


@pytest.mark.parametrize("expr", [
    "X_20_30",
    "M_45_20",
    "M_20_30_AC",
    "M_20_30_ABC",
    "M_20_30_CB",
    "M_20",
    "m_20_30",
])
def test_parse_audience_invalid(expr) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        parse_audience(expr)


@pytest.mark.parametrize("birth, ref, expected", [
    ("30.06.1980", "2025-06-30", 45),
    ("01.07.1980", "2025-06-30", 44),
    ("29.02.2000", "2025-02-28", 24),
    ("29.02.2000", "2025-03-01", 25),
    ("29.02.2000", "2024-02-28", 23),
    ("29.02.2000", "2024-02-29", 24),
])
def test_full_years(birth, ref, expected) -> None:
    b = pd.Series(pd.to_datetime([birth], format="%d.%m.%Y"))
    assert int(full_years(b, pd.Timestamp(ref)).iloc[0]) == expected


REF = pd.Timestamp("2025-06-30")


@pytest.fixture
def resp() -> pd.DataFrame:
    return pd.DataFrame({
        "id": ["a", "b", "c", "d", "e", "f"],
        "gender": ["M", "M", "W", "W", "M", "W"],
        "birth_date": pd.to_datetime(
            ["1990-06-30", "1990-07-01", "2000-01-01",
             "1980-01-01", "1970-01-01", "1960-01-01"]
        ),
        "income_group": ["B", "B", "C", "A", "B", "B"],
    })


def ids(df: pd.DataFrame) -> set[str]:
    return set(df["id"])


def test_select_both_age_bounds_inclusive(resp) -> None:
    assert ids(select_audience(resp, Audience("ALL", 34, 35, frozenset()), REF)) == {"a", "b"}


def test_select_upper_bound_excludes_older(resp) -> None:
    assert ids(select_audience(resp, Audience("ALL", 35, 35, frozenset()), REF)) == {"a"}


def test_select_open_interval_and_gender(resp) -> None:
    assert ids(select_audience(resp, Audience("M", 55, None, frozenset()), REF)) == {"e"}


def test_select_income_group(resp) -> None:
    assert ids(select_audience(resp, Audience("W", 25, 45, frozenset({"B", "C"})), REF)) == {"c"}


def test_select_empty(resp) -> None:
    assert select_audience(resp, Audience("M", 99, None, frozenset()), REF).empty


def test_audience_is_immutable_and_hashable() -> None:
    audience = Audience("M", 25, 40, frozenset({"B"}))
    with pytest.raises(FrozenInstanceError):
        setattr(audience, "gender", "W")
    assert hash(audience) == hash(Audience("M", 25, 40, frozenset({"B"})))
