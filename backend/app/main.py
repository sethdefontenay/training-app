"""FastAPI application entrypoint."""

from fastapi import APIRouter, FastAPI

from app.api import auth, tracking, workouts
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Training App API",
    version="0.1.0",
    docs_url="/docs",
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

app.include_router(api_v1)
