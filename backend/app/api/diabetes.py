"""Diabetes record endpoints (Tidepool pull + record view). Seth's own record."""

import json
from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, SessionDep
from app.clock import local_today
from app.integrations.health import IntegrationNotConfigured
from app.integrations.tidepool import (
    TidepoolClient,
    TidepoolProvider,
    glucose_summary,
    insulin_count,
    parse_tidepool_export,
    store_points,
    sync_diabetes,
)
from app.services.settings import tidepool_config

router = APIRouter(prefix="/diabetes", tags=["diabetes"])


async def get_tidepool_provider(session: SessionDep) -> TidepoolProvider:
    cfg = await tidepool_config(session)
    return TidepoolClient(email=cfg["email"], password=cfg["password"])


ProviderDep = Annotated[TidepoolProvider, Depends(get_tidepool_provider)]


@router.post("/sync")
async def sync(
    session: SessionDep,
    user: CurrentUser,
    provider: ProviderDep,
    days: int = 7,
    before: date | None = None,
) -> dict[str, object]:
    end = before or local_today()
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


@router.post("/upload")
async def upload(
    session: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> dict[str, int]:
    """Ingest a Tidepool data-model JSON export directly (no Tidepool cloud needed)."""
    try:
        data = json.loads(await file.read())
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON file") from e
    if not isinstance(data, list):
        raise HTTPException(
            status_code=400, detail="Expected a JSON array of Tidepool data objects"
        )
    glucose, insulin = parse_tidepool_export(data)
    g_added, i_added = await store_points(session, glucose, insulin)
    return {"glucose_added": g_added, "insulin_added": i_added}


@router.get("/record")
async def record(
    session: SessionDep, user: CurrentUser, days: int = 7, before: date | None = None
) -> dict[str, object]:
    end = before or local_today()
    start = end - timedelta(days=days - 1)
    insulin = await insulin_count(session, start, end)
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "glucose": await glucose_summary(session, start, end),
        "insulin_events": insulin,
        "pump_uploaded": insulin > 0,
    }
