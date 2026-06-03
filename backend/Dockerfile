# Multi-stage build using uv.
FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install deps first for layer caching.
COPY pyproject.toml ./
COPY uv.lock* ./
RUN uv sync --no-dev --no-install-project

# App code + migrations (needed to run alembic on boot).
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --no-dev

EXPOSE 8000
# Run migrations, then serve on Railway's $PORT (default 8000 locally).
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
