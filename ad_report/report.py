"""Заполнение шаблона презентации."""

import os
import sys

import pandas as pd
from pptx import Presentation
from pptx.chart.chart import Chart
from pptx.chart.data import CategoryChartData
from pptx.shapes.autoshape import Shape
from pptx.table import Table
from pptx.text.text import _Paragraph

from ad_report.audience import Audience
from ad_report.periods import Month


MONTH_NAMES = [
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
]


GENDER_TEXT = {"M": "мужчины", "W": "женщины", "ALL": "все респонденты"}


INCOME_TEXT = {
    "A": "с доходом ниже среднего",
    "B": "со средним доходом",
    "C": "с доходом выше среднего",
    "AB": "с доходом ниже среднего и средним",
    "BC": "со средним и высоким доходом",
}


def describe_audience(audience: Audience) -> str:
    parts = [GENDER_TEXT[audience.gender]]
    if audience.age_max is None:
        parts.append(f"от {audience.age_min} лет")
    else:
        parts.append(f"от {audience.age_min} до {audience.age_max} лет")
    if audience.income:
        parts.append(INCOME_TEXT["".join(sorted(audience.income))])
    return " ".join(parts)


def describe_period(month_from: Month, month_to: Month) -> str:
    def fmt(ym: Month) -> str:
        return f"{MONTH_NAMES[ym[1] - 1]} {ym[0]}"

    if month_from == month_to:
        return fmt(month_from)
    return f"{fmt(month_from)} – {fmt(month_to)}"


def set_paragraph_text(paragraph: _Paragraph, text: str) -> None:
    """Пишет текст в первый run абзаца, остальные run удаляет (форматирование сохраняется)."""
    runs = paragraph.runs
    if runs:
        runs[0].text = text
        for run in runs[1:]:
            run._r.getparent().remove(run._r)
    else:
        paragraph.add_run().text = text


def fill_subtitle(shape: Shape, audience_text: str, period_text: str) -> None:
    paragraphs = shape.text_frame.paragraphs
    set_paragraph_text(paragraphs[0], f"Целевая аудитория: {audience_text}")
    set_paragraph_text(paragraphs[1], f"Период: {period_text}")


def fill_table(table: Table, top: pd.DataFrame) -> None:
    """Строки 1-5: рекламодатель и охват. Лишние строки (если рекламодателей меньше) очищаются."""
    for i in range(1, len(table.rows)):
        if i - 1 < len(top):
            name = top.loc[i - 1, "advertiser"]
            value = f"{top.loc[i - 1, 'reach']:.2f}%"
        else:
            name, value = "", ""
        set_paragraph_text(table.cell(i, 0).text_frame.paragraphs[0], name)
        set_paragraph_text(table.cell(i, 1).text_frame.paragraphs[0], value)


def fill_chart(chart: Chart, trp: pd.DataFrame) -> None:
    data = CategoryChartData()
    data.categories = [f"{month:02d}.{year}" for year, month in trp.index]
    for advertiser in trp.columns:
        data.add_series(advertiser, [float(v) for v in trp[advertiser]])
    chart.replace_data(data)


def build_report(
    template_path: str,
    output_path: str,
    audience_text: str,
    period_text: str,
    top: pd.DataFrame,
    trp: pd.DataFrame,
) -> None:
    prs = Presentation(template_path)
    fill_subtitle(prs.slides[0].shapes[1], audience_text, period_text)
    fill_table(prs.slides[1].shapes[1].table, top)
    fill_chart(prs.slides[2].shapes[1].chart, trp)

    try:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        prs.save(output_path)
    except OSError as exc:
        sys.exit(
            f"Ошибка: не удалось сохранить презентацию в {output_path}: "
            f"{exc.strerror or exc}. Возможно, файл открыт в другой программе"
        )
