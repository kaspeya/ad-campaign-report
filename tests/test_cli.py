import sys
from typing import Any

import pytest

from ad_report import cli, data
from ad_report.audience import Audience
from ad_report.cli import parse_args, run
from ad_report.nlp import NlpError


def test_run_reports_missing_input_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ad_report.config.RESPONDENTS_PATH", str(tmp_path / "respondents.csv"))
    monkeypatch.setattr("ad_report.config.VIEWS_PATH", str(tmp_path / "views.csv"))
    with pytest.raises(SystemExit) as exc:
        run(Audience("ALL", 18, 35, frozenset()), (2024, 1), (2024, 6), "o.pptx")
    assert "respondents.csv" in str(exc.value.code)
    assert "views.csv" in str(exc.value.code)


def test_parse_args_custom_audience_type() -> None:
    args = parse_args(["любой текст", "01.2024", "06.2025", "out.pptx"],
                      audience_type=str)
    assert args.audience == "любой текст"
    assert args.month_from == (2024, 1)


def test_parse_args_validates_months_with_custom_type() -> None:
    with pytest.raises(SystemExit):
        parse_args(["любой текст", "06.2025", "01.2025", "out.pptx"],
                   audience_type=str)


def test_run_reports_directory_instead_of_file(monkeypatch, tmp_path) -> None:
    (tmp_path / "views.csv").mkdir()
    (tmp_path / "respondents.csv").write_text("id\n")
    monkeypatch.setattr("ad_report.config.RESPONDENTS_PATH", str(tmp_path / "respondents.csv"))
    monkeypatch.setattr("ad_report.config.VIEWS_PATH", str(tmp_path / "views.csv"))
    with pytest.raises(SystemExit) as exc:
        run(Audience("ALL", 18, 35, frozenset()), (2024, 1), (2024, 6), "o.pptx")
    assert "views.csv" in str(exc.value.code)
    assert "respondents.csv" not in str(exc.value.code)


@pytest.fixture
def input_files_present(monkeypatch) -> None:
    monkeypatch.setattr(data, "check_input_files", lambda: None)


def set_argv(monkeypatch, *args) -> None:
    monkeypatch.setattr(sys, "argv", ["main_nlp.py", *args])


def test_main_nlp_runs_with_recognized_audience(monkeypatch, capsys, input_files_present) -> None:
    captured: dict[str, Any] = {}
    audience = Audience("M", 25, 40, frozenset({"B"}))
    monkeypatch.setattr(cli, "audience_from_text", lambda text: ("M_25_40_B", audience))
    monkeypatch.setattr(cli, "run", lambda *args: captured.setdefault("args", args))
    set_argv(monkeypatch, "Мужчины от 25 до 40 со средним доходом", "01.2024", "06.2025", "o.pptx")

    cli.main_nlp()

    assert captured["args"] == (audience, (2024, 1), (2025, 6), "o.pptx")
    out = capsys.readouterr().out
    assert "Распознана аудитория: M_25_40_B" in out
    assert "мужчины от 25 до 40 лет со средним доходом" in out


def test_main_nlp_reports_nlp_error(monkeypatch, input_files_present) -> None:
    def fail(text):
        raise NlpError("нет ключа")

    monkeypatch.setattr(cli, "audience_from_text", fail)
    set_argv(monkeypatch, "текст", "01.2024", "06.2025", "o.pptx")
    with pytest.raises(SystemExit) as exc:
        cli.main_nlp()
    assert str(exc.value.code) == "Ошибка: нет ключа"


def test_main_nlp_validates_period_before_calling_model(monkeypatch) -> None:
    called = []
    monkeypatch.setattr(cli, "audience_from_text", lambda text: called.append(text))
    set_argv(monkeypatch, "текст", "06.2025", "01.2025", "o.pptx")
    with pytest.raises(SystemExit):
        cli.main_nlp()
    assert called == []


def test_main_nlp_checks_input_files_before_calling_model(monkeypatch, tmp_path) -> None:
    called = []
    monkeypatch.setattr("ad_report.config.RESPONDENTS_PATH", str(tmp_path / "respondents.csv"))
    monkeypatch.setattr("ad_report.config.VIEWS_PATH", str(tmp_path / "views.csv"))
    monkeypatch.setattr(cli, "audience_from_text", lambda text: called.append(text))
    set_argv(monkeypatch, "текст", "01.2024", "06.2025", "o.pptx")
    with pytest.raises(SystemExit) as exc:
        cli.main_nlp()
    assert "не найдены входные файлы" in str(exc.value.code)
    assert called == []
