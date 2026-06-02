"""Manual sync trigger for steps + sleep (also intended for scheduled + on-open runs)."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.integrations.health import (
    GoogleHealthProvider,
    HealthProvider,
    IntegrationNotConfigured,
    sync_steps_sleep,
)

router = APIRouter(prefix="/sync", tags=["sync"])


def get_health_provider() -> HealthProvider:
    return GoogleHealthProvider()


ProviderDep = Annotated[HealthProvider, Depends(get_health_provider)]


@router.post("/steps-sleep")
async def sync_health(
    session: SessionDep,
    user: CurrentUser,
    provider: ProviderDep,
    days: int = 7,
) -> dict[str, object]:
    end = date.today()
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
