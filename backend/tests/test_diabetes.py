"""diabetes_data.feature: Tidepool pull, glucose summary, missing pump, idempotency.

Uses a FIXED reference date via ?before= so the window is deterministic (CI-safe).
"""

from datetime import date, datetime, time

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.diabetes import get_tidepool_provider
from app.integrations.tidepool import GlucosePoint, InsulinPoint
from app.main import app

REF = date(2026, 5, 25)
PARAMS = {"days": 1, "before": REF.isoformat()}


def _at(hour: int) -> datetime:
    return datetime.combine(REF, time(hour, 0))


class FakeTidepool:
    def __init__(self, glucose: list[GlucosePoint], insulin: list[InsulinPoint]) -> None:
        self._g = glucose
        self._i = insulin

    async def fetch(self, start: date, end: date) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
        return self._g, self._i


def _use(glucose: list[GlucosePoint], insulin: list[InsulinPoint]) -> None:
    app.dependency_overrides[get_tidepool_provider] = lambda: FakeTidepool(glucose, insulin)


async def test_sync_stores_glucose_and_insulin(auth_client: AsyncClient) -> None:
    _use([GlucosePoint(_at(8), 6.5)], [InsulinPoint(_at(8), "bolus", 4.0, carbs_g=74)])
    body = (await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)).json()
    assert body["glucose_synced"] == 1
    assert body["insulin_synced"] == 1
    assert body["pump_uploaded"] is True


async def test_glucose_summary_avg_and_tir(auth_client: AsyncClient) -> None:
    _use([GlucosePoint(_at(8), 5.0), GlucosePoint(_at(9), 12.0)], [])
    await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)
    rec = (await auth_client.get("/api/v1/diabetes/record", params=PARAMS)).json()
    assert rec["glucose"]["count"] == 2
    assert rec["glucose"]["average"] == 8.5
    assert rec["glucose"]["time_in_range_pct"] == 50.0


async def test_missing_pump_upload_shown_honestly(auth_client: AsyncClient) -> None:
    _use([GlucosePoint(_at(8), 6.0)], [])  # glucose only, no pump upload
    await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)
    rec = (await auth_client.get("/api/v1/diabetes/record", params=PARAMS)).json()
    assert rec["pump_uploaded"] is False
    assert rec["insulin_events"] == 0


async def test_resync_idempotent(auth_client: AsyncClient, session: AsyncSession) -> None:
    _use([GlucosePoint(_at(8), 6.0)], [])
    await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)
    await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)
    from sqlalchemy import func, select

    from app.models import GlucoseReading

    count = await session.scalar(select(func.count()).select_from(GlucoseReading))
    assert count == 1


async def test_unconfigured_surfaces_503(auth_client: AsyncClient) -> None:
    app.dependency_overrides.pop(get_tidepool_provider, None)
    resp = await auth_client.post("/api/v1/diabetes/sync", params=PARAMS)
    assert resp.status_code == 503


def test_parse_tidepool_export() -> None:
    from app.integrations.tidepool import parse_tidepool_export

    data = [
        {"type": "cbg", "value": 421, "units": "mg/dL", "time": "2026-05-25T08:00:00Z"},
        {"type": "smbg", "value": 6.5, "units": "mmol/L", "time": "2026-05-25T09:00:00Z"},
        {"type": "bolus", "subType": "normal", "normal": 7.75, "time": "2026-05-25T08:05:00Z"},
        {"type": "basal", "rate": 0.8, "time": "2026-05-25T00:00:00Z"},
    ]
    glucose, insulin = parse_tidepool_export(data)
    assert len(glucose) == 2
    assert glucose[0].mmol_l == round(421 / 18.0182, 1)  # mg/dL -> mmol/L
    assert len(insulin) == 2
    assert any(p.units == 7.75 for p in insulin)


async def test_upload_ingests_export(auth_client: AsyncClient) -> None:
    import json

    payload = [
        {"type": "cbg", "value": 6.0, "units": "mmol/L", "time": "2026-05-25T08:00:00Z"},
        {"type": "bolus", "subType": "normal", "normal": 4.0, "time": "2026-05-25T08:05:00Z"},
    ]
    files = {"file": ("export.json", json.dumps(payload).encode(), "application/json")}
    resp = await auth_client.post("/api/v1/diabetes/upload", files=files)
    assert resp.status_code == 200
    assert resp.json() == {"glucose_added": 1, "insulin_added": 1}

    resp2 = await auth_client.post("/api/v1/diabetes/upload", files=files)
    assert resp2.json() == {"glucose_added": 0, "insulin_added": 0}  # deduped
