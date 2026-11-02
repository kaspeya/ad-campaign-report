"""Командная строка и запуск расчёта."""

import argparse
import sys
from collections.abc import Callable
from typing import Any

from ad_report import config, data
from ad_report.audience import Audience, parse_audience, select_audience
from ad_report.metrics import ad_reach, monthly_trp, top_advertisers
from ad_report.nlp import NlpError, audience_from_text
from ad_report.periods import Month, month_range, parse_month, period_bounds, reference_date
from ad_report.report import build_report, describe_audience, describe_period


def parse_args(
    argv: list[str] | None = None,
    audience_type: Callable[[str], Any] = parse_audience,
    audience_help: str = "например M_25_40_B",
) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Отчёт по рекламным кампаниям: охват и TRP для заданной ЦА"
    )
    parser.add_argument("audience", type=audience_type, help=audience_help)
    parser.add_argument("month_from", type=parse_month, help="MM.YYYY")
    parser.add_argument("month_to", type=parse_month, help="MM.YYYY")
    parser.add_argument("output", help="путь к итоговому .pptx")
    args = parser.parse_args(argv)

    if args.month_from > args.month_to:
        parser.error("нижняя граница диапазона месяцев позже верхней")
    if not args.output.lower().endswith(".pptx"):
        parser.error("путь для сохранения должен заканчиваться на .pptx")
    return args


def run(audience: Audience, month_from: Month, month_to: Month, output: str) -> None:
    data.check_input_files()

    resp = data.load_respondents(config.RESPONDENTS_PATH)
    ref = reference_date(*month_to)
    audience_df = select_audience(resp, audience, ref)
    if audience_df.empty:
        sys.exit("Ошибка: в заданную целевую аудиторию не попал ни один респондент")

    views = data.load_views(config.VIEWS_PATH)
    start, end = period_bounds(month_from, month_to)
    audience_ids = set(audience_df["id"])

    reach = ad_reach(views, audience_ids, start, end)
    if reach.empty:
        sys.exit("Ошибка: в указанном периоде нет данных о просмотрах")
    top = top_advertisers(reach)
    months = month_range(month_from, month_to)
    trp = monthly_trp(views, audience_ids, list(top["advertiser"]), months, start, end)

    build_report(
        config.TEMPLATE_PATH,
        output,
        describe_audience(audience),
        describe_period(month_from, month_to),
        top,
        trp,
    )
    print(f"Готово: {output} (размер ЦА: {len(audience_df)})")


def main() -> None:
    args = parse_args()
    run(args.audience, args.month_from, args.month_to, args.output)


def main_nlp() -> None:
    args = parse_args(
        audience_type=str,
        audience_help="описание аудитории на естественном языке, например "
        "'Мужчины от 25 до 40 со средним доходом'",
    )
    data.check_input_files()
    try:
        expression, audience = audience_from_text(args.audience)
    except NlpError as exc:
        sys.exit(f"Ошибка: {exc}")
    print(f"Распознана аудитория: {expression} ({describe_audience(audience)})")
    run(audience, args.month_from, args.month_to, args.output)
