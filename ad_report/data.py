"""Загрузка CSV и проверка входных файлов."""

import os
import sys

import pandas as pd

from ad_report import config


def load_respondents(path: str) -> pd.DataFrame:
    resp = pd.read_csv(path)
    resp["birth_date"] = pd.to_datetime(resp["birth_date"], format="%d.%m.%Y")
    return resp


def load_views(path: str) -> pd.DataFrame:
    views = pd.read_csv(path)
    views["date"] = pd.to_datetime(views["date"], format="%d.%m.%Y")
    return views


def check_input_files() -> None:
    required = (config.RESPONDENTS_PATH, config.VIEWS_PATH, config.TEMPLATE_PATH)
    missing = [p for p in required if not os.path.isfile(p)]
    if missing:
        names = ", ".join(os.path.basename(p) for p in missing)
        sys.exit(
            f"Ошибка: не найдены входные файлы (или вместо файла папка): {names}. "
            "Положите их рядом с main.py (см. README)"
        )
