# Backend: python:3.12-slim + uv. Запуск: uvicorn app.main:app на :8000
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Сначала только манифесты — слой с зависимостями кешируется отдельно от кода.
# uv.lock* — glob: если lock ещё не сгенерирован, COPY не упадёт (pyproject.toml всегда есть).
COPY pyproject.toml .python-version uv.lock* ./
RUN uv sync --no-dev --no-install-project

COPY app ./app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
