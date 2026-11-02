import argparse
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from ad_report.audience import Audience
from ad_report.nlp import (
    NlpError,
    _is_network_error,
    ask_llm,
    audience_from_text,
    build_expression,
    call_with_retry,
    extract_json,
)


@pytest.mark.parametrize("data, expected", [
    ({"gender": "M", "age_min": 25, "age_max": 40, "income": ["B"]}, "M_25_40_B"),
    ({"gender": "W", "age_min": 25, "age_max": 45, "income": ["B", "C"]}, "W_25_45_BC"),
    ({"gender": "M", "age_min": 60, "age_max": None, "income": ["A"]}, "M_60+_A"),
    ({"gender": "ALL", "age_min": None, "age_max": None, "income": []}, "ALL_0+"),
    ({"gender": "M", "age_min": 41, "age_max": None, "income": []}, "M_41+"),
    ({"gender": "W", "age_min": None, "age_max": 29, "income": ["C"]}, "W_0_29_C"),
    ({"gender": "ALL", "age_min": 18, "age_max": 35, "income": ["A", "B", "C"]}, "ALL_18_35"),
    ({"gender": "W", "age_min": 30, "age_max": 50, "income": ["C", "B"]}, "W_30_50_BC"),
    ({"gender": "m", "age_min": 25, "age_max": 40, "income": []}, "M_25_40"),
    ({}, "ALL_0+"),
    ({"gender": "M", "age_min": 20, "age_max": 30, "income": "BC"}, "M_20_30_BC"),
    ({"gender": None, "age_min": 18, "age_max": 35}, "ALL_18_35"),
])
def test_build_expression_valid(data, expected) -> None:
    assert build_expression(data) == expected


@pytest.mark.parametrize("data", [
    {"gender": "X", "age_min": 20, "age_max": 30},
    {"gender": 5, "age_min": 20, "age_max": 30},
    {"gender": "M", "age_min": "25", "age_max": 40},
    {"gender": "M", "age_min": 25.5, "age_max": 40},
    {"gender": "M", "age_min": True, "age_max": 40},
    {"gender": "M", "age_min": -5, "age_max": 40},
    {"gender": "M", "age_min": 20, "age_max": "40"},
    {"gender": "M", "age_min": 50, "age_max": 30},
    {"gender": "M", "age_min": 20, "income": ["A", "C"]},
    {"gender": "M", "age_min": 20, "income": ["D"]},
    {"gender": "M", "age_min": 20, "income": 5},
])
def test_build_expression_invalid(data) -> None:
    with pytest.raises(NlpError):
        build_expression(data)


@pytest.mark.parametrize("raw, expected", [
    ('{"gender": "M"}', {"gender": "M"}),
    ('Вот ответ: {"gender": "M"} Спасибо!', {"gender": "M"}),
    ('```json\n{"gender": "W", "age_min": 1}\n```', {"gender": "W", "age_min": 1}),
])
def test_extract_json_valid(raw, expected) -> None:
    assert extract_json(raw) == expected


@pytest.mark.parametrize("raw", ["нет никакого json", '{"gender": }', "{не json}"])
def test_extract_json_invalid(raw) -> None:
    with pytest.raises(NlpError):
        extract_json(raw)


def test_audience_from_text_ok() -> None:
    def stub(text):
        return '{"gender": "M", "age_min": 25, "age_max": 40, "income": ["B"]}'

    expression, audience = audience_from_text("любой текст", ask=stub)
    assert expression == "M_25_40_B"
    assert audience == Audience("M", 25, 40, frozenset({"B"}))


def test_audience_from_text_passes_text_to_model() -> None:
    seen = []

    def stub(text):
        seen.append(text)
        return '{"gender": "ALL"}'

    audience_from_text("Все от 18", ask=stub)
    assert seen == ["Все от 18"]


def test_audience_from_text_empty_description() -> None:
    with pytest.raises(NlpError):
        audience_from_text("   ", ask=lambda text: "{}")


def test_audience_from_text_garbage_from_model() -> None:
    with pytest.raises(NlpError):
        audience_from_text("текст", ask=lambda text: "не знаю, что ответить")


def test_audience_from_text_rejected_by_parse_audience(monkeypatch) -> None:
    def reject(expression):
        raise argparse.ArgumentTypeError("плохо")

    monkeypatch.setattr("ad_report.nlp.parse_audience", reject)
    with pytest.raises(NlpError, match="недопустимую аудиторию"):
        audience_from_text("текст", ask=lambda text: '{"gender": "M"}')


def test_retry_once_then_success() -> None:
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionError("обрыв")
        return "ok"

    assert call_with_retry(flaky, is_retryable=lambda exc: True, delay=0) == "ok"
    assert len(calls) == 2


def test_retry_gives_up_after_two_attempts() -> None:
    calls = []

    def always_fails():
        calls.append(1)
        raise ConnectionError("обрыв")

    with pytest.raises(ConnectionError):
        call_with_retry(always_fails, is_retryable=lambda exc: True, delay=0)
    assert len(calls) == 2


def test_retry_skips_non_retryable() -> None:
    calls = []

    def fails():
        calls.append(1)
        raise ValueError("не сеть")

    with pytest.raises(ValueError):
        call_with_retry(fails, is_retryable=lambda exc: False, delay=0)
    assert len(calls) == 1


@pytest.mark.parametrize("exc, expected", [
    (httpx.ConnectTimeout("таймаут"), True),
    (httpx.ReadTimeout("таймаут"), True),
    (httpx.ConnectError("обрыв"), True),
    (httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] bad"), False),
    (ValueError("не сеть"), False),
])
def test_is_network_error(exc, expected) -> None:
    assert _is_network_error(exc) is expected


GIGA_ENV = (
    "GIGACHAT_SCOPE",
    "GIGACHAT_MODEL",
    "GIGACHAT_BASE_URL",
    "GIGACHAT_CA_BUNDLE",
    "GIGACHAT_VERIFY_SSL",
)


def reply(text: str) -> SimpleNamespace:
    message = SimpleNamespace(content=text)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def giga(monkeypatch) -> dict[str, Any]:
    state: dict[str, Any] = {"kwargs": None, "payload": None, "calls": 0, "script": []}

    class FakeGigaChat:
        def __init__(self, **kwargs):
            state["kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def chat(self, payload):
            state["calls"] += 1
            state["payload"] = payload
            result = state["script"].pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    monkeypatch.setattr("gigachat.GigaChat", FakeGigaChat)
    monkeypatch.setattr("ad_report.nlp.time.sleep", lambda seconds: None)
    monkeypatch.setenv("GIGACHAT_AUTH_KEY", "test-key")
    for name in GIGA_ENV:
        monkeypatch.delenv(name, raising=False)
    return state


def test_ask_llm_requires_key(giga, monkeypatch) -> None:
    monkeypatch.delenv("GIGACHAT_AUTH_KEY")
    with pytest.raises(NlpError, match="GIGACHAT_AUTH_KEY"):
        ask_llm("текст")
    assert giga["calls"] == 0


def test_ask_llm_defaults(giga) -> None:
    giga["script"] = [reply('{"gender": "M"}')]
    assert ask_llm("текст") == '{"gender": "M"}'
    assert giga["kwargs"] == {
        "credentials": "test-key",
        "scope": "GIGACHAT_API_PERS",
        "model": "GigaChat-3-Pro",
    }
    payload = giga["payload"]
    assert payload["temperature"] == 0
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][-1] == {"role": "user", "content": "текст"}


def test_ask_llm_env_overrides(giga, monkeypatch) -> None:
    monkeypatch.setenv("GIGACHAT_MODEL", "GigaChat-3-Ultra")
    monkeypatch.setenv("GIGACHAT_SCOPE", "GIGACHAT_API_B2B")
    monkeypatch.setenv("GIGACHAT_BASE_URL", "https://example.test")
    monkeypatch.setenv("GIGACHAT_CA_BUNDLE", "cert.pem")
    giga["script"] = [reply("{}")]
    ask_llm("текст")
    assert giga["kwargs"] == {
        "credentials": "test-key",
        "scope": "GIGACHAT_API_B2B",
        "model": "GigaChat-3-Ultra",
        "base_url": "https://example.test",
        "ca_bundle_file": "cert.pem",
    }


def test_ask_llm_verify_ssl_false_warns(giga, monkeypatch, capsys) -> None:
    monkeypatch.setenv("GIGACHAT_VERIFY_SSL", "false")
    giga["script"] = [reply("{}")]
    ask_llm("текст")
    assert giga["kwargs"]["verify_ssl_certs"] is False
    assert "SSL" in capsys.readouterr().err


def test_ask_llm_retries_network_error_once(giga) -> None:
    giga["script"] = [httpx.ConnectTimeout("таймаут"), reply('{"gender": "M"}')]
    assert ask_llm("текст") == '{"gender": "M"}'
    assert giga["calls"] == 2


def test_ask_llm_does_not_retry_other_errors(giga) -> None:
    giga["script"] = [RuntimeError("404 Not Found")]
    with pytest.raises(NlpError, match="ошибка запроса"):
        ask_llm("текст")
    assert giga["calls"] == 1


def test_ask_llm_certificate_error_hint_without_retry(giga) -> None:
    giga["script"] = [httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] self-signed")]
    with pytest.raises(NlpError, match="GIGACHAT_CA_BUNDLE"):
        ask_llm("текст")
    assert giga["calls"] == 1


def test_ask_llm_empty_choices(giga) -> None:
    giga["script"] = [SimpleNamespace(choices=[])]
    with pytest.raises(NlpError, match="пустой ответ"):
        ask_llm("текст")
