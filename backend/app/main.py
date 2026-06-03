"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import (
    auth,
    checkin,
    daily,
    diabetes,
    plans,
    shopping,
    sync,
    tracking,
    workouts,
)
from app.api import (
    settings as settings_api,
)
from app.config import get_settings
from app.seed import create_user

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # First-deploy convenience: create/refresh the single user from env vars.
    if settings.seed_email and settings.seed_password:
        await create_user(settings.seed_email, settings.seed_password)
    yield


app = FastAPI(
    title="Training App API",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — proves the service is up through the whole pipeline."""
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


# Versioned API surface. Use a router (NOT a mounted sub-app) so dependency overrides
# and shared middleware apply uniformly.
api_v1 = APIRouter(prefix="/api/v1")


@api_v1.get("/ping", tags=["meta"])
async def ping() -> dict[str, str]:
    return {"pong": "ok"}


api_v1.include_router(auth.router)
api_v1.include_router(workouts.router)
api_v1.include_router(tracking.router)
api_v1.include_router(daily.router)
api_v1.include_router(shopping.router)
api_v1.include_router(checkin.router)
api_v1.include_router(sync.router)
api_v1.include_router(diabetes.router)
api_v1.include_router(plans.router)
api_v1.include_router(settings_api.router)

app.include_router(api_v1)

# Serve the built PWA (single-service prod deploy) if a build was copied in.
# Mounted last so it never shadows /health, /docs, or /api/v1/*. Skipped in local dev
# (no ./static dir) where Vite serves the frontend instead.
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="spa")
