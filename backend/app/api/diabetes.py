"""Diabetes record endpoints (Tidepool pull + record view). Seth's own record."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.integrations.health import IntegrationNotConfigured
from app.integrations.tidepool import (
    TidepoolClient,
    TidepoolProvider,
    glucose_summary,
    insulin_count,
    sync_diabetes,
)

router = APIRouter(prefix="/diabetes", tags=["diabetes"])


def get_tidepool_provider() -> TidepoolProvider:
    return TidepoolClient()


ProviderDep = Annotated[TidepoolProvider, Depends(get_tidepool_provider)]


@router.post("/sync")
async def sync(
    session: SessionDep, user: CurrentUser, provider: ProviderDep, days: int = 7
) -> dict[str, object]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    try:
        result = await sync_diabetes(session, provider, start, end)
    except IntegrationNotConfigured as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tidepool not yet implemented (needs credentials)",
        ) from e
    return {
        "glucose_synced": result.glucose,
        "insulin_synced": result.insulin,
        "pump_uploaded": result.pump_uploaded,
    }


@router.get("/record")
async def record(session: SessionDep, user: CurrentUser, days: int = 7) -> dict[str, object]:
    end = date.today()
    start = end - timedelta(days=days - 1)
    insulin = await insulin_count(session, start, end)
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "glucose": await glucose_summary(session, start, end),
        "insulin_events": insulin,
        "pump_uploaded": insulin > 0,
    }
