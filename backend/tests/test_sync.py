"""health_sync_steps_sleep.feature: pull, backfill, idempotent, manual override, failure."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.sync import get_health_provider
from app.integrations.health import SleepRecord, StepRecord
from app.main import app
from app.models import StepsDay


class FakeProvider:
    def __init__(self, steps: list[StepRecord], sleeps: list[SleepRecord]) -> None:
        self._steps = steps
        self._sleeps = sleeps

    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]:
        return self._steps, self._sleeps


def _use_provider(steps: list[StepRecord], sleeps: list[SleepRecord]) -> None:
    app.dependency_overrides[get_health_provider] = lambda: FakeProvider(steps, sleeps)


async def test_sync_stores_steps_and_sleep(auth_client: AsyncClient) -> None:
    _use_provider(
        [StepRecord(date(2026, 5, 25), 733, 7000)],
        [SleepRecord(date(2026, 5, 25), asleep_min=472.5, efficiency=98.0)],
    )
    resp = await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["steps_synced"] == 1
    assert body["sleep_synced"] == 1


async def test_backfill_multiple_days(auth_client: AsyncClient) -> None:
    _use_provider(
        [
            StepRecord(date(2026, 5, 23), 5000, 7000),
            StepRecord(date(2026, 5, 24), 6000, 7000),
            StepRecord(date(2026, 5, 25), 8000, 7000),
        ],
        [],
    )
    body = (await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 3})).json()
    assert body["steps_synced"] == 3


async def test_resync_is_idempotent(auth_client: AsyncClient, session: AsyncSession) -> None:
    _use_provider([StepRecord(date(2026, 5, 25), 733, 7000)], [])
    await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 1})
    await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 1})
    from sqlalchemy import func, select

    count = await session.scalar(select(func.count()).select_from(StepsDay))
    assert count == 1


async def test_manual_entry_not_overwritten(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    session.add(StepsDay(date=date(2026, 5, 25), steps=8200, manual=True))
    await session.commit()
    _use_provider([StepRecord(date(2026, 5, 25), 733, 7000)], [])
    body = (await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 1})).json()
    assert "2026-05-25" in body["preserved_manual"]
    from sqlalchemy import select

    row = await session.scalar(select(StepsDay).where(StepsDay.date == date(2026, 5, 25)))
    assert row is not None and row.steps == 8200  # manual value preserved


async def test_unconfigured_provider_surfaces_503(auth_client: AsyncClient) -> None:
    # No override -> real GoogleHealthProvider raises IntegrationNotConfigured.
    app.dependency_overrides.pop(get_health_provider, None)
    resp = await auth_client.post("/api/v1/sync/steps-sleep", params={"days": 1})
    assert resp.status_code == 503
