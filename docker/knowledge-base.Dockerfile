# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY pyproject.toml uv.lock ./

COPY knowledge-base/pyproject.toml knowledge-base/README.md ./knowledge-base/
COPY knowledge-base/src ./knowledge-base/src

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

WORKDIR /app/knowledge-base

# Default command runs the FastAPI server
# Override with celery command for worker: 
#   uv run celery -A knowledge_base.celery_app worker --loglevel=info
CMD ["uv", "run", "uvicorn", "knowledge_base.app:app", "--host", "0.0.0.0", "--port", "8001"]
