"""FastAPI application entrypoint."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    assistant,
    auth,
    checkin,
    daily,
    diabetes,
    imports,
    invites,
    plans,
    shopping,
    sleep,
    sync,
    tracking,
    workouts,
)
from app.api import (
    settings as settings_api,
)
from app.api.deps import require_capability
from app.config import get_settings
from app.seed import create_user

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # First-deploy convenience: create/refresh the single user from env vars.
    if settings.seed_email and settings.seed_password:
        await create_user(settings.seed_email, settings.seed_password)
    if settings.mcp_token:
        # Keep the MCP Streamable-HTTP session manager running for the app's lifetime.
        from app.assistant.mcp_server import session_manager

        async with session_manager().run():
            yield
    else:
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

# Capability-gated dependencies for the owner-only surfaces. Default-off flags mean an
# invited (standard) user is denied these entirely; the owner has them all on.
_diabetes_only = [Depends(require_capability("has_diabetes"))]
_health_only = [Depends(require_capability("has_health_integrations"))]
_checkins_only = [Depends(require_capability("has_checkins"))]


@api_v1.get("/ping", tags=["meta"])
async def ping() -> dict[str, str]:
    return {"pong": "ok"}


# Universal surface (every user): workouts, tracking, daily, shopping, assistant.
api_v1.include_router(auth.router)
api_v1.include_router(invites.router)
api_v1.include_router(workouts.router)
api_v1.include_router(tracking.router)
api_v1.include_router(daily.router)
api_v1.include_router(shopping.router)
api_v1.include_router(plans.router)
api_v1.include_router(imports.router)
api_v1.include_router(assistant.router)

# Owner-only surface, gated by per-user capability flags.
api_v1.include_router(checkin.router, dependencies=_checkins_only)
api_v1.include_router(sync.router, dependencies=_health_only)
api_v1.include_router(settings_api.router, dependencies=_health_only)
api_v1.include_router(sleep.router, dependencies=_health_only)
api_v1.include_router(diabetes.router, dependencies=_diabetes_only)

app.include_router(api_v1)

# Expose the assistant's tools as an authed MCP server (Streamable HTTP) for external
# clients. Mounted BEFORE the SPA catch-all so /mcp isn't swallowed; gated on MCP_TOKEN.
if settings.mcp_token:
    from starlette.routing import Mount

    from app.assistant.mcp_server import bearer_guard, mcp_asgi

    app.router.routes.append(Mount("/mcp", app=bearer_guard(mcp_asgi, settings.mcp_token)))

# Serve the built PWA (single-service prod deploy) if a build was copied in.
# Mounted last so it never shadows /health, /docs, or /api/v1/*. Skipped in local dev
# (no ./static dir) where Vite serves the frontend instead.
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    _assets = _static_dir / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        # Real file (sw.js, manifest, favicon, …) -> serve it; otherwise the SPA's
        # index.html so client-side routes (e.g. /settings) work on hard navigation.
        if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json"}:
            raise HTTPException(status_code=404)
        candidate = (_static_dir / full_path).resolve()
        if (
            full_path
            and candidate.is_file()
            and str(candidate).startswith(str(_static_dir.resolve()))
        ):
            return FileResponse(candidate)
        return FileResponse(_static_dir / "index.html")
