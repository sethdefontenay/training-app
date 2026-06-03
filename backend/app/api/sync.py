"""Manual sync trigger for steps + sleep (also intended for scheduled + on-open runs)."""

from datetime import datetime, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.config import get_settings
from app.integrations.health import (
    GoogleHealthProvider,
    HealthProvider,
    IntegrationNotConfigured,
    sync_steps_sleep,
)
from app.services.settings import google_health_config

router = APIRouter(prefix="/sync", tags=["sync"])
_settings = get_settings()


async def get_health_provider(session: SessionDep) -> HealthProvider:
    cfg = await google_health_config(session)
    return GoogleHealthProvider(
        client_id=cfg["client_id"],
        client_secret=cfg["client_secret"],
        refresh_token=cfg["refresh_token"],
        tz=_settings.timezone,
    )


ProviderDep = Annotated[HealthProvider, Depends(get_health_provider)]


@router.post("/steps-sleep")
async def sync_health(
    session: SessionDep,
    user: CurrentUser,
    provider: ProviderDep,
    days: int = 7,
) -> dict[str, object]:
    # "Today" in the user's timezone, not the server's UTC clock — otherwise the
    # window trails a day for UTC+ users and never writes a row for their today.
    end = datetime.now(ZoneInfo(_settings.timezone)).date()
    start = end - timedelta(days=days - 1)
    try:
        result = await sync_steps_sleep(session, provider, start, end)
    except IntegrationNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health provider not yet implemented (needs credentials)",
        ) from e
    return {
        "steps_synced": result.steps_synced,
        "sleep_synced": result.sleep_synced,
        "preserved_manual": result.preserved_manual,
    }
