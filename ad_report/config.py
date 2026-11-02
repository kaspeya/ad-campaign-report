"""Настройки: пути к файлам и значения по умолчанию для GigaChat."""

import os
from collections.abc import Mapping


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_data_dir(environ: Mapping[str, str] = os.environ) -> str:
    """Каталог с CSV: переменная DATA_DIR или папка со скриптом."""
    return environ.get("DATA_DIR") or BASE_DIR


DATA_DIR = resolve_data_dir()
RESPONDENTS_PATH = os.path.join(DATA_DIR, "respondents.csv")
VIEWS_PATH = os.path.join(DATA_DIR, "views.csv")
TEMPLATE_PATH = os.path.join(BASE_DIR, "presentation_template.pptx")

GIGACHAT_MODEL = "GigaChat-3-Pro"
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
RETRY_ATTEMPTS = 2
RETRY_DELAY = 1.0
