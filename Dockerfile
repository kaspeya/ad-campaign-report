FROM python:3.13-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py main_nlp.py presentation_template.pptx ./
COPY ad_report ad_report

FROM base AS test
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY tests tests
COPY pyproject.toml .flake8 ./
RUN flake8 && isort --check-only --diff . && pytest -q

FROM base AS final
ENTRYPOINT ["python"]
CMD ["main.py", "--help"]

