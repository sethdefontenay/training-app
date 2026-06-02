"""diabetes_data.feature: Tidepool pull, glucose summary, missing pump, idempotency."""

from datetime import date, datetime, time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diabetes import get_tidepool_provider
from app.integrations.tidepool import GlucosePoint, InsulinPoint
from app.main import app

TODAY = date.today()


def _at(hour: int) -> datetime:
    return datetime.combine(TODAY, time(hour, 0))


class FakeTidepool:
    def __init__(self, glucose: list[GlucosePoint], insulin: list[InsulinPoint]) -> None:
        self._g = glucose
        self._i = insulin

    async def fetch(self, start: date, end: date) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
        return self._g, self._i


def _use(glucose: list[GlucosePoint], insulin: list[InsulinPoint]) -> None:
    app.dependency_overrides[get_tidepool_provider] = lambda: FakeTidepool(glucose, insulin)


async def test_sync_stores_glucose_and_insulin(auth_client: AsyncClient) -> None:
    _use(
        [GlucosePoint(_at(8), 6.5)],
        [InsulinPoint(_at(8), "bolus", 4.0, carbs_g=74)],
    )
    body = (await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})).json()
    assert body["glucose_synced"] == 1
    assert body["insulin_synced"] == 1
    assert body["pump_uploaded"] is True


async def test_glucose_summary_avg_and_tir(auth_client: AsyncClient) -> None:
    _use([GlucosePoint(_at(8), 5.0), GlucosePoint(_at(9), 12.0)], [])
    await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})
    rec = (await auth_client.get("/api/v1/diabetes/record", params={"days": 1})).json()
    assert rec["glucose"]["count"] == 2
    assert rec["glucose"]["average"] == 8.5
    assert rec["glucose"]["time_in_range_pct"] == 50.0


async def test_missing_pump_upload_shown_honestly(auth_client: AsyncClient) -> None:
    _use([GlucosePoint(_at(8), 6.0)], [])  # glucose only, no pump upload
    await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})
    rec = (await auth_client.get("/api/v1/diabetes/record", params={"days": 1})).json()
    assert rec["pump_uploaded"] is False
    assert rec["insulin_events"] == 0


async def test_resync_idempotent(auth_client: AsyncClient, session: AsyncSession) -> None:
    _use([GlucosePoint(_at(8), 6.0)], [])
    await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})
    await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})
    from sqlalchemy import func, select

    from app.models import GlucoseReading

    count = await session.scalar(select(func.count()).select_from(GlucoseReading))
    assert count == 1


async def test_unconfigured_surfaces_503(auth_client: AsyncClient) -> None:
    app.dependency_overrides.pop(get_tidepool_provider, None)
    resp = await auth_client.post("/api/v1/diabetes/sync", params={"days": 1})
    assert resp.status_code == 503
