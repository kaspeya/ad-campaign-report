import pandas as pd
import pytest
from pptx import Presentation

from ad_report.audience import Audience
from ad_report.config import TEMPLATE_PATH
from ad_report.report import build_report, describe_audience, describe_period


@pytest.mark.parametrize("audience, expected", [
    (Audience("M", 25, 40, frozenset({"B"})), "мужчины от 25 до 40 лет со средним доходом"),
    (Audience("ALL", 18, 35, frozenset()), "все респонденты от 18 до 35 лет"),
    (Audience("M", 60, None, frozenset({"A"})), "мужчины от 60 лет с доходом ниже среднего"),
    (Audience("W", 25, 45, frozenset({"B", "C"})),
     "женщины от 25 до 45 лет со средним и высоким доходом"),
])
def test_describe_audience(audience, expected) -> None:
    assert describe_audience(audience) == expected


@pytest.mark.parametrize("month_from, month_to, expected", [
    ((2024, 1), (2025, 6), "январь 2024 – июнь 2025"),
    ((2026, 3), (2026, 3), "март 2026"),
])
def test_describe_period(month_from, month_to, expected) -> None:
    assert describe_period(month_from, month_to) == expected


def test_build_report_end_to_end(tmp_path) -> None:
    names = ["A", "B", "C", "D", "E"]
    top = pd.DataFrame({"advertiser": names, "reach": [5.0, 4.0, 3.0, 2.0, 1.0]})
    index = pd.MultiIndex.from_tuples([(2024, 1), (2024, 2), (2024, 3)])
    trp = pd.DataFrame({n: [1.0, 2.0, 3.0] for n in names}, index=index)

    out = tmp_path / "новая_папка" / "report.pptx"
    build_report(TEMPLATE_PATH, str(out), "все респонденты от 18 до 35 лет",
                 "январь 2024 – март 2024", top, trp)
    assert out.exists()

    prs = Presentation(str(out))
    assert prs.slides[0].shapes[1].text_frame.text == (
        "Целевая аудитория: все респонденты от 18 до 35 лет\n"
        "Период: январь 2024 – март 2024"
    )
    table = prs.slides[1].shapes[1].table
    assert [table.cell(i, 0).text for i in range(1, 6)] == names
    assert table.cell(1, 1).text == "5.00%"
    chart = prs.slides[2].shapes[1].chart
    assert list(chart.plots[0].categories) == ["01.2024", "02.2024", "03.2024"]
    assert [s.name for s in chart.plots[0].series] == names


def test_build_report_unwritable_output(tmp_path) -> None:
    names = ["A", "B", "C", "D", "E"]
    top = pd.DataFrame({"advertiser": names, "reach": [5.0, 4.0, 3.0, 2.0, 1.0]})
    index = pd.MultiIndex.from_tuples([(2024, 1), (2024, 2)])
    trp = pd.DataFrame({n: [1.0, 2.0] for n in names}, index=index)

    target = tmp_path / "busy.pptx"
    target.mkdir()

    with pytest.raises(SystemExit) as exc:
        build_report(TEMPLATE_PATH, str(target), "аудитория", "период", top, trp)
    assert "не удалось сохранить" in str(exc.value.code)
