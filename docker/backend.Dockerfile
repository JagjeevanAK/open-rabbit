# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./


COPY agent/pyproject.toml agent/README.md ./agent/
COPY agent/src ./agent/src

COPY backend/pyproject.toml backend/README.md ./backend/
COPY backend/src ./backend/src
COPY backend/alembic ./backend/alembic
COPY backend/alembic.ini ./backend/

# Sync all workspace dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

WORKDIR /app/backend

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
