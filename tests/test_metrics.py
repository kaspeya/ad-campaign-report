import pandas as pd
import pytest

from ad_report.metrics import ad_reach, monthly_trp, top_advertisers
from ad_report.periods import month_range


def make_views(rows: list[tuple[str, str, str, str]]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=["date", "advertiser", "ad_id", "respondent_id"])
    df["date"] = pd.to_datetime(df["date"])
    df.insert(0, "id", [f"v{i}" for i in range(len(df))])
    return df


START, END = pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31")


@pytest.fixture
def reach() -> pd.Series:
    views = make_views([
        ("2024-01-10", "X", "ad1", "a"),
        ("2024-01-11", "X", "ad1", "a"),
        ("2024-01-12", "X", "ad1", "b"),
        ("2024-01-10", "X", "ad2", "z"),
        ("2024-01-01", "Y", "ad3", "a"),
        ("2024-01-31", "Y", "ad3", "b"),
        ("2024-01-15", "Y", "ad3", "c"),
        ("2024-01-15", "Y", "ad3", "d"),
        ("2024-02-01", "Y", "ad4", "a"),
        ("2023-12-31", "Y", "ad5", "a"),
    ])
    out = ad_reach(views, {"a", "b", "c", "d"}, START, END)
    return out.set_index("ad_id")["reach"]


def test_reach_repeat_views_do_not_increase(reach) -> None:
    assert reach["ad1"] == pytest.approx(50.0)


def test_reach_ad_without_audience_views_has_zero(reach) -> None:
    assert reach["ad2"] == 0


def test_reach_period_boundaries_inclusive(reach) -> None:
    assert reach["ad3"] == pytest.approx(100.0)


def test_reach_ads_outside_period_excluded(reach) -> None:
    assert set(reach.index) == {"ad1", "ad2", "ad3"}


def make_reach(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["ad_id", "advertiser", "reach"])


def test_top_order_and_tie_by_name() -> None:
    r = make_reach([
        ("1", "B", 10.0), ("2", "A", 10.0), ("3", "C", 30.0), ("4", "D", 5.0),
    ])
    top = top_advertisers(r, n=3)
    assert list(top["advertiser"]) == ["C", "A", "B"]
    assert list(top["reach"]) == [30.0, 10.0, 10.0]


def test_top_averages_over_ads_including_zero() -> None:
    r = make_reach([("1", "B", 20.0), ("2", "B", 0.0), ("3", "A", 9.0)])
    top = top_advertisers(r)
    assert list(top["advertiser"]) == ["B", "A"]
    assert top.loc[0, "reach"] == pytest.approx(10.0)


@pytest.fixture
def trp() -> pd.DataFrame:
    views = make_views([
        ("2024-01-05", "X", "x1", "a"),
        ("2024-01-20", "X", "x1", "a"),
        ("2024-01-21", "X", "x2", "b"),
        ("2024-01-22", "X", "x1", "z"),
        ("2024-01-23", "Y", "y1", "a"),
        ("2024-03-10", "X", "x1", "a"),
    ])
    months = month_range((2024, 1), (2024, 3))
    return monthly_trp(
        views, {"a", "b"}, ["X", "W"], months,
        pd.Timestamp("2024-01-01"), pd.Timestamp("2024-03-31"),
    )


def test_trp_counts_repeats_and_ignores_outsiders(trp) -> None:
    assert trp.loc[(2024, 1), "X"] == pytest.approx(150.0)
    assert trp.loc[(2024, 3), "X"] == pytest.approx(50.0)


def test_trp_month_without_views_is_zero(trp) -> None:
    assert trp.loc[(2024, 2), "X"] == 0
    assert (trp["W"] == 0).all()


def test_trp_columns_alphabetical_and_all_months_present(trp) -> None:
    assert list(trp.columns) == ["W", "X"]
    assert list(trp.index) == [(2024, 1), (2024, 2), (2024, 3)]
