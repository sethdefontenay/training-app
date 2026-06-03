# Single-service production image: build the PWA, serve it from the FastAPI backend.
# Railway: set this service's Root Directory to the repo root (uses this Dockerfile).

# --- Stage 1: build the frontend ---
FROM node:20-slim AS web
WORKDIR /web
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build  # -> /web/dist

# --- Stage 2: backend + bundled SPA ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Backend deps (layer-cached).
COPY backend/pyproject.toml ./
COPY backend/uv.lock* ./
RUN uv sync --no-dev --no-install-project

# Backend code + migrations.
COPY backend/app ./app
COPY backend/alembic.ini ./
COPY backend/migrations ./migrations
RUN uv sync --no-dev

# Built PWA, served by FastAPI at "/" (see app/main.py).
COPY --from=web /web/dist ./static

EXPOSE 8000
# Apply migrations, then serve on Railway's $PORT.
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
