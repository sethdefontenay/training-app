"""Steps + sleep sync (ported from google-health / catch_up.py).

The provider boundary is abstracted so it can be mocked in tests and swapped for the
real Google Health client once credentials are wired. The sync itself is idempotent and
never silently overwrites a manual entry.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import SleepNight, StepsDay


class IntegrationNotConfigured(RuntimeError):
    """Raised when the real provider lacks credentials."""


@dataclass
class StepRecord:
    date: date
    steps: int
    target_steps: int | None = None


@dataclass
class SleepRecord:
    date: date
    asleep_min: float | None = None
    efficiency: float | None = None
    bedtime: str | None = None
    wake_time: str | None = None


class HealthProvider(Protocol):
    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]: ...


class GoogleHealthProvider:
    """Real provider. Code-complete shell — raises until Google creds are wired."""

    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]:
        settings = get_settings()
        # The real implementation authenticates with Google and pulls steps + sleep.
        # Until credentials exist we fail loudly rather than inventing data.
        if not getattr(settings, "google_health_token", None):
            raise IntegrationNotConfigured("Google Health credentials not configured")
        raise NotImplementedError  # pragma: no cover


@dataclass
class SyncResult:
    steps_synced: int = 0
    sleep_synced: int = 0
    preserved_manual: list[str] = field(default_factory=list)


async def sync_steps_sleep(
    session: AsyncSession, provider: HealthProvider, start: date, end: date
) -> SyncResult:
    steps, sleeps = await provider.fetch(start, end)
    result = SyncResult()

    for rec in steps:
        row = await session.scalar(select(StepsDay).where(StepsDay.date == rec.date))
        if row is not None and row.manual:
            result.preserved_manual.append(rec.date.isoformat())
            continue
        if row is None:
            row = StepsDay(date=rec.date)
            session.add(row)
        row.steps = rec.steps
        if rec.target_steps is not None:
            row.target_steps = rec.target_steps
            row.target_met = rec.steps >= rec.target_steps
        result.steps_synced += 1

    for night in sleeps:
        srow = await session.scalar(select(SleepNight).where(SleepNight.date == night.date))
        if srow is not None and srow.manual:
            continue
        if srow is None:
            srow = SleepNight(date=night.date)
            session.add(srow)
        srow.asleep_min = night.asleep_min
        srow.efficiency = night.efficiency
        srow.bedtime = night.bedtime
        srow.wake_time = night.wake_time
        result.sleep_synced += 1

    await session.commit()
    return result
