"""Расчёт охвата и TRP."""

import pandas as pd

from ad_report.periods import Month


def ad_reach(
    views: pd.DataFrame, audience_ids: set[str], start: pd.Timestamp, end: pd.Timestamp
) -> pd.DataFrame:
    """Охват (в процентах) каждого ролика, у которого есть просмотры в периоде.

    Ролик попадает в период, если его хоть раз смотрел кто угодно.
    Ролики без просмотров из ЦА получают охват 0.
    Возвращает DataFrame: ad_id, advertiser, reach.
    """
    in_period = views[(views["date"] >= start) & (views["date"] <= end)]
    ads = in_period[["ad_id", "advertiser"]].drop_duplicates().copy()

    aud_views = in_period[in_period["respondent_id"].isin(audience_ids)]
    unique_viewers = aud_views.groupby("ad_id")["respondent_id"].nunique()

    ads["reach"] = ads["ad_id"].map(unique_viewers).fillna(0) / len(audience_ids) * 100
    return ads


def top_advertisers(reach: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """Топ-n рекламодателей по среднему охвату роликов.

    При равенстве охвата сортируем по названию.
    """
    avg = reach.groupby("advertiser", as_index=False)["reach"].mean()
    avg = avg.sort_values(["reach", "advertiser"], ascending=[False, True])
    return avg.head(n).reset_index(drop=True)


def monthly_trp(
    views: pd.DataFrame,
    audience_ids: set[str],
    advertisers: list[str],
    months: list[Month],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """TRP по месяцам: строки это месяцы (год, месяц), столбцы это рекламодатели.

    Учитываются все просмотры людьми из ЦА, включая повторные.
    Месяцы без просмотров получают 0.
    """
    v = views[
        (views["date"] >= start)
        & (views["date"] <= end)
        & views["respondent_id"].isin(audience_ids)
        & views["advertiser"].isin(advertisers)
    ]
    counts = v.groupby(
        ["advertiser", v["date"].dt.year.rename("year"), v["date"].dt.month.rename("month")]
    ).size()

    columns = sorted(advertisers)
    table = pd.DataFrame(0.0, index=pd.MultiIndex.from_tuples(months), columns=columns)
    for (adv, year, month), n in counts.items():
        table.loc[(year, month), adv] = n / len(audience_ids) * 100
    return table
