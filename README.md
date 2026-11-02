# Анализ рекламных кампаний: охват и TRP

Консольная утилита строит презентацию по шаблону: топ-5 рекламодателей по охвату целевой аудитории (ЦА) и их TRP по месяцам.

## Установка

Python 3.13+. Проверено на 3.13 (в Docker) и на 3.15.

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

В Linux и macOS вместо второй команды: `source .venv/bin/activate`.

## Данные

`respondents.csv` и `views.csv` в репозиторий не входят. Скачайте их на [Яндекс Диске](https://disk.yandex.ru/d/ryXzFNpM4yfIPw) (необходим пароль) и положите в корень проекта, рядом с `main.py` (другой каталог можно указать переменной `DATA_DIR`).

## Запуск

```
python main.py M_25_40_B 01.2024 06.2025 output/report.pptx
```

Аргументы: выражение ЦА `{gender}_{age}` или `{gender}_{age}_{income_group}` (например, `ALL_18_35`, `W_25_45_BC`, `M_60+_A`), нижняя и верхняя границы месяцев `MM.YYYY`, путь для сохранения `.pptx`.

## NLP-интерфейс (дополнительное задание)

```
$env:GIGACHAT_AUTH_KEY = Read-Host "Введите ключ"
python main_nlp.py "Мужчины от 25 до 40 со средним доходом" 01.2024 06.2025 output/report.pptx
```

Параметры аудитории извлекает GigaChat (бесплатный Freemium, developers.sber.ru). Перед расчётом утилита печатает, как поняла описание. «Старше 40» читается как 41+. В Linux и macOS ключ задаётся так: `export GIGACHAT_AUTH_KEY=...`.

Настройка через переменные окружения. Ключ передаётся только так, в код и в образ он не попадает.

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `GIGACHAT_AUTH_KEY` | ключ авторизации (обязательна для NLP) | — |
| `GIGACHAT_MODEL` | модель | `GigaChat-3-Pro` |
| `GIGACHAT_SCOPE` | область доступа | `GIGACHAT_API_PERS` |
| `GIGACHAT_BASE_URL` | адрес API | адрес из SDK |
| `GIGACHAT_CA_BUNDLE` | путь к файлу сертификата | — |
| `GIGACHAT_VERIFY_SSL` | `false` отключает проверку сертификата (на свой риск) | включена |
| `DATA_DIR` | каталог с CSV | корень проекта |

Если запрос падает с ошибкой проверки сертификата, укажите `GIGACHAT_CA_BUNDLE` или, на свой риск, `GIGACHAT_VERIFY_SSL=false`.

## Тесты и проверки

```
pip install -r requirements-dev.txt
pytest
flake8
isort --check-only --diff .
mypy main.py main_nlp.py ad_report tests
```

## Структура проекта

```
main.py, main_nlp.py   точки входа
ad_report/
  config.py            пути и настройки по умолчанию
  audience.py          разбор выражения ЦА, отбор респондентов
  periods.py           месяцы и границы периода
  data.py              загрузка CSV, проверка входных файлов
  metrics.py           охват и TRP
  report.py            заполнение шаблона презентации
  cli.py               аргументы командной строки, запуск
  nlp.py               распознавание ЦА через GigaChat
tests/                 тесты по модулям
```

## Принятые решения

- Возраст считается в полных годах на последний день последнего месяца диапазона, поэтому числа могут отличаться от образца в шаблоне. Родившиеся 29 февраля в невисокосный год отмечают день рождения 1 марта.
- Ролик входит в период, если у него есть просмотр в периоде от любого респондента; ролик, который не смотрел никто из ЦА, имеет охват 0. Охват рекламодателя — среднее по его роликам.
- При равном охвате рекламодатели идут по алфавиту; месяц без просмотров в графике равен 0.
- Пустая ЦА, период без просмотров, неверные аргументы и отсутствие входных файлов дают сообщение об ошибке, презентация при этом не создаётся.

## Запуск в Docker (альтернативный способ)

Нужен Docker с Compose. Оба CSV должны лежать в корне проекта: если файла нет, Docker создаст на его месте пустую папку. Закройте открытые презентации из `output`.

```
docker compose build
docker compose run --rm app main.py M_25_40_B 01.2024 06.2025 output/report.pptx
```

NLP-интерфейс (ключ берётся из окружения терминала, остальные `GIGACHAT_*` передаются так же):

```
$env:GIGACHAT_AUTH_KEY = Read-Host "Введите ключ"
docker compose run --rm app main_nlp.py "Мужчины от 25 до 40 со средним доходом" 01.2024 06.2025 output/report.pptx
```

Без Compose (PowerShell):

```
docker build -t ad-report .
docker run --rm -v "${PWD}\respondents.csv:/data/respondents.csv:ro" -v "${PWD}\views.csv:/data/views.csv:ro" -v "${PWD}\output:/app/output" ad-report main.py M_25_40_B 01.2024 06.2025 output/report.pptx
```

Тесты и проверка стиля в образе: `docker build --target test -t ad-report:test .`
