ARG PYTHON_VERSION=3.13-slim
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv

FROM python:${PYTHON_VERSION}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY src ./src
COPY dados ./dados

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    DATABASE_PATH=/app/data/residencial_aurora.sqlite3

EXPOSE 8000

CMD ["uvicorn", "residencial_aurora.api:app", "--host", "0.0.0.0", "--port", "8000"]
