"""Sleep endpoints: per-night stage timeline + weekly trend."""

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.clock import local_today
from app.services.sleep import latest_night_date, night_view, trend

router = APIRouter(prefix="/sleep", tags=["sleep"])


@router.get("/night")
async def night(
    session: SessionDep,
    user: CurrentUser,
    date_: Annotated[date | None, Query(alias="date")] = None,
) -> dict[str, object]:
    day = date_ or await latest_night_date(session) or local_today()
    return await night_view(session, day)


@router.get("/trend")
async def sleep_trend(session: SessionDep, user: CurrentUser, days: int = 7) -> dict[str, object]:
    end = local_today()
    start = end - timedelta(days=days - 1)
    return await trend(session, start, end)
