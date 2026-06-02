"""FastAPI application entrypoint."""

from fastapi import FastAPI

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


# Versioned API surface lives under /api/v1 (routers added per feature phase).
api_v1 = FastAPI(title="Training App API v1", version="0.1.0")


@api_v1.get("/ping", tags=["meta"])
async def ping() -> dict[str, str]:
    return {"pong": "ok"}


app.mount("/api/v1", api_v1)
