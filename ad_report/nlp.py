"""Извлечение параметров целевой аудитории из текста на естественном языке (GigaChat)."""

import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable
from typing import Any, TypeVar

from ad_report.audience import Audience, parse_audience
from ad_report.config import GIGACHAT_MODEL, GIGACHAT_SCOPE, RETRY_ATTEMPTS, RETRY_DELAY


SYSTEM_PROMPT = """Ты извлекаешь параметры целевой аудитории из описания на русском языке.
Верни ТОЛЬКО один JSON-объект без пояснений и без форматирования, строго такого вида:
{"gender": "M" | "W" | "ALL", "age_min": число или null, "age_max": число или null,
 "income": список из букв "A", "B", "C"}

Правила:
- gender: "M" для мужчин, "W" для женщин, "ALL", если пол не указан или речь обо всех.
- age_min и age_max: целые числа, границы включаются.
  "от 25 до 40" -> age_min 25, age_max 40.
  "от 40" и "40 и старше" -> age_min 40, age_max null.
  "старше 40" -> age_min 41, age_max null.
  "до 30" -> age_min null, age_max 30.
  "младше 30" -> age_min null, age_max 29.
  Возраст не указан -> оба null.
- income: "A" это доход ниже среднего (низкий), "B" средний, "C" выше среднего (высокий).
  "средний и высокий" -> ["B", "C"]. Доход не указан или любой -> [].
- Ничего не выдумывай: если параметр не назван, оставляй значение по умолчанию.

Пример. Описание: "Женщины от 25 до 45 лет со средним и высоким доходом".
Ответ: {"gender": "W", "age_min": 25, "age_max": 45, "income": ["B", "C"]}"""


JSON_RE = re.compile(r"\{.*}", re.DOTALL)


class NlpError(Exception):
    """Ошибка NLP-интерфейса с сообщением, понятным пользователю."""


T = TypeVar("T")


def _is_network_error(exc: Exception) -> bool:
    """Сетевой сбой, который имеет смысл повторить (таймаут, обрыв соединения)."""
    if "CERTIFICATE_VERIFY_FAILED" in str(exc):
        return False
    try:
        import httpx
    except ImportError:
        return False
    return isinstance(
        exc, (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)
    )


def call_with_retry(
    func: Callable[[], T],
    is_retryable: Callable[[Exception], bool] = _is_network_error,
    attempts: int = RETRY_ATTEMPTS,
    delay: float = RETRY_DELAY,
) -> T:
    """Вызывает func; при ошибке, которую is_retryable считает сетевой, повторяет."""
    for _ in range(attempts - 1):
        try:
            return func()
        except Exception as exc:
            if not is_retryable(exc):
                raise
            time.sleep(delay)
    return func()


def _env_flag_false(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"0", "false", "no", "off"}


def ask_llm(text: str) -> str:
    """Отправляет описание аудитории в GigaChat и возвращает сырой текст ответа."""
    key = os.environ.get("GIGACHAT_AUTH_KEY")
    if not key:
        raise NlpError(
            "не задана переменная окружения GIGACHAT_AUTH_KEY (ключ авторизации GigaChat API)"
        )

    kwargs: dict[str, Any] = {
        "credentials": key,
        "scope": os.environ.get("GIGACHAT_SCOPE", GIGACHAT_SCOPE),
        "model": os.environ.get("GIGACHAT_MODEL", GIGACHAT_MODEL),
    }
    if os.environ.get("GIGACHAT_BASE_URL"):
        kwargs["base_url"] = os.environ["GIGACHAT_BASE_URL"]
    if os.environ.get("GIGACHAT_CA_BUNDLE"):
        kwargs["ca_bundle_file"] = os.environ["GIGACHAT_CA_BUNDLE"]
    if _env_flag_false("GIGACHAT_VERIFY_SSL"):
        kwargs["verify_ssl_certs"] = False
        print("Предупреждение: проверка SSL-сертификатов отключена", file=sys.stderr)

    try:
        from gigachat import GigaChat
    except ImportError as exc:
        raise NlpError("не установлен пакет gigachat: pip install -r requirements.txt") from exc

    payload = {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }

    def attempt() -> Any:
        with GigaChat(**kwargs) as client:
            return client.chat(payload)

    try:
        response = call_with_retry(attempt)
    except Exception as exc:
        message = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in message:
            raise NlpError(
                "не удалось проверить SSL-сертификат сервера GigaChat. Укажите файл сертификата "
                "в GIGACHAT_CA_BUNDLE или (на свой риск) задайте GIGACHAT_VERIFY_SSL=false"
            ) from exc
        raise NlpError(f"ошибка запроса к GigaChat: {type(exc).__name__}: {message[:200]}") from exc

    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError) as exc:
        raise NlpError("GigaChat вернул пустой ответ") from exc


def extract_json(raw: str) -> dict[str, Any]:
    """Вырезает первый JSON-объект из ответа модели (она может обернуть его в текст или код-блок)"""
    match = JSON_RE.search(raw)
    if not match:
        raise NlpError(f"модель не вернула JSON: {raw[:100]!r}")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise NlpError(f"модель вернула некорректный JSON: {match.group(0)[:100]!r}") from exc
    if not isinstance(data, dict):
        raise NlpError("модель вернула JSON не в виде объекта")
    return data


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NlpError(f"поле {name} в ответе модели должно быть целым неотрицательным: {value!r}")
    return value


def build_expression(data: dict[str, Any]) -> str:
    """Собирает выражение ЦА ({gender}_{age}[_{income}]) из ответа модели."""
    gender = data.get("gender") or "ALL"
    if not isinstance(gender, str) or gender.upper() not in {"M", "W", "ALL"}:
        raise NlpError(f"модель вернула неизвестный пол: {gender!r}")
    gender = gender.upper()

    age_min = data.get("age_min")
    age_min = 0 if age_min is None else _as_int(age_min, "age_min")
    age_max = data.get("age_max")
    age_max = None if age_max is None else _as_int(age_max, "age_max")
    if age_max is not None and age_min > age_max:
        raise NlpError(f"нижняя граница возраста ({age_min}) больше верхней ({age_max})")

    income_raw = data.get("income") or []
    if isinstance(income_raw, str):
        income_raw = list(income_raw)
    if not isinstance(income_raw, list) or any(x not in {"A", "B", "C"} for x in income_raw):
        raise NlpError(f"модель вернула недопустимые группы дохода: {income_raw!r}")
    letters = set(income_raw)
    if letters == {"A", "B", "C"}:
        letters = set()
    income = "".join(sorted(letters))
    if income == "AC":
        raise NlpError(
            "группы дохода «ниже среднего» и «выше среднего» без «среднего» "
            "задать нельзя (комбинация AC запрещена)"
        )

    age_part = f"{age_min}+" if age_max is None else f"{age_min}_{age_max}"
    return f"{gender}_{age_part}" + (f"_{income}" if income else "")


def audience_from_text(
    text: str, ask: Callable[[str], str] | None = None
) -> tuple[str, Audience]:
    """Описание на естественном языке -> (выражение ЦА, разобранная аудитория)."""
    if not text.strip():
        raise NlpError("описание аудитории пустое")
    ask = ask or ask_llm
    expression = build_expression(extract_json(ask(text)))
    try:
        audience = parse_audience(expression)
    except argparse.ArgumentTypeError as exc:
        raise NlpError(f"модель вернула недопустимую аудиторию {expression!r}: {exc}") from exc
    return expression, audience
