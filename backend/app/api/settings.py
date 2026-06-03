"""Settings endpoints: manage integration connections from the UI."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUser, SessionDep
from app.services.settings import (
    GOOGLE_HEALTH_FIELDS,
    google_health_config,
    set_setting,
)

router = APIRouter(prefix="/settings", tags=["settings"])


class GoogleHealthIn(BaseModel):
    api_key: str | None = None


async def _gh_status(session: SessionDep) -> dict[str, object]:
    cfg = await google_health_config(session)
    # Never echo secret values back — only whether each field is set.
    return {
        "connected": bool(cfg["api_key"]),
        "fields": [
            {"key": k, "label": label, "set": bool(cfg[k])} for k, label in GOOGLE_HEALTH_FIELDS
        ],
    }


@router.get("/google-health")
async def google_health_status(session: SessionDep, user: CurrentUser) -> dict[str, object]:
    return await _gh_status(session)


@router.put("/google-health")
async def google_health_save(
    body: GoogleHealthIn, session: SessionDep, user: CurrentUser
) -> dict[str, object]:
    for key, _ in GOOGLE_HEALTH_FIELDS:
        value = getattr(body, key)
        if value is not None:
            await set_setting(session, f"google_health.{key}", value)
    await session.commit()
    return await _gh_status(session)
