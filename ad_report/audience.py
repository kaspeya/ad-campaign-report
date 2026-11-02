"""Целевая аудитория: разбор выражения и отбор респондентов."""

import argparse
import calendar
import re
from dataclasses import dataclass

import pandas as pd


AUDIENCE_RE = re.compile(
    r"^(?P<gender>M|W|ALL)"
    r"_(?:(?P<age_min>\d+)_(?P<age_max>\d+)|(?P<age_open>\d+)\+)"
    r"(?:_(?P<income>A|B|C|AB|BC))?$"
)


@dataclass(frozen=True)
class Audience:
    """Целевая аудитория: пол, границы возраста (включительно) и группы дохода.

    age_max = None для открытого интервала (55+).
    income = пустое множество, если доход не ограничен.
    """

    gender: str
    age_min: int
    age_max: int | None
    income: frozenset[str]


def parse_audience(expr: str) -> Audience:
    """Разбирает выражение ЦА вида M_25_40_B."""
    m = AUDIENCE_RE.match(expr)
    if not m:
        raise argparse.ArgumentTypeError(
            f"неверное выражение ЦА '{expr}'. Формат: {{gender}}_{{age}} или "
            "{gender}_{age}_{income}, например ALL_18_35, M_60+_A, W_25_45_BC "
            "(gender: M, W, ALL; income: A, B, C, AB, BC)"
        )
    if m["age_open"] is not None:
        age_min, age_max = int(m["age_open"]), None
    else:
        age_min, age_max = int(m["age_min"]), int(m["age_max"])
        if age_min > age_max:
            raise argparse.ArgumentTypeError(
                f"в выражении ЦА '{expr}' нижняя граница возраста больше верхней"
            )
    income = frozenset(m["income"]) if m["income"] else frozenset()
    return Audience(m["gender"], age_min, age_max, income)


def full_years(birth: pd.Series, ref: pd.Timestamp) -> pd.Series:
    """Возраст в полных годах на дату ref.

    birth: Series с датами рождения, ref: pd.Timestamp.
    """
    years = ref.year - birth.dt.year
    b_month = birth.dt.month
    b_day = birth.dt.day

    if not calendar.isleap(ref.year):
        feb29 = (b_month == 2) & (b_day == 29)
        b_month = b_month.mask(feb29, 3)
        b_day = b_day.mask(feb29, 1)

    not_yet = (b_month > ref.month) | ((b_month == ref.month) & (b_day > ref.day))
    return years - not_yet.astype(int)


def select_audience(resp: pd.DataFrame, audience: Audience, ref: pd.Timestamp) -> pd.DataFrame:
    age = full_years(resp["birth_date"], ref)
    mask = age >= audience.age_min
    if audience.age_max is not None:
        mask &= age <= audience.age_max
    if audience.gender != "ALL":
        mask &= resp["gender"] == audience.gender
    if audience.income:
        mask &= resp["income_group"].isin(audience.income)
    return resp[mask]
