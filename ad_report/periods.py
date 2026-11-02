"""Месяцы и границы периода отчёта."""

import argparse
import re

import pandas as pd


Month = tuple[int, int]
MONTH_RE = re.compile(r"^(0[1-9]|1[0-2])\.(\d{4})$")


def parse_month(s: str) -> Month:
    """'MM.YYYY' -> (год, месяц)."""
    m = MONTH_RE.match(s)
    if not m:
        raise argparse.ArgumentTypeError(
            f"неверный месяц '{s}'. Формат: MM.YYYY, например 03.2026"
        )
    return int(m.group(2)), int(m.group(1))


def reference_date(year: int, month: int) -> pd.Timestamp:
    """Последний день месяца."""
    return pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(0)


def period_bounds(month_from: Month, month_to: Month) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Первый день month_from и последний день month_to (включительно)."""
    start = pd.Timestamp(month_from[0], month_from[1], 1)
    end = reference_date(*month_to)
    return start, end


def month_range(month_from: Month, month_to: Month) -> list[Month]:
    """Список пар (год, месяц) от month_from до month_to включительно."""
    months = []
    year, month = month_from
    while (year, month) <= month_to:
        months.append((year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return months
