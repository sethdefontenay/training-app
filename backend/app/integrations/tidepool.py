"""Diabetes data (Dexcom glucose + Tandem pump) via Tidepool.

Single integration boundary, mockable for tests. Stored to Seth's OWN record (not the
PT package). Pulled at check-in time and on opening the diabetes record. A missing pump
upload is surfaced honestly (pump_uploaded=False) — never fabricated.
⚠️ Real Tidepool API auth to be verified against live docs before wiring credentials.
"""

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.health import IntegrationNotConfigured
from app.models import GlucoseReading, InsulinEvent

# Standard CGM time-in-range band (mmol/L).
TIR_LOW = 3.9
TIR_HIGH = 10.0


@dataclass
class GlucosePoint:
    ts: datetime
    mmol_l: float


@dataclass
class InsulinPoint:
    ts: datetime
    kind: str
    units: float
    carbs_g: float | None = None


class TidepoolProvider(Protocol):
    async def fetch(
        self, start: date, end: date
    ) -> tuple[list[GlucosePoint], list[InsulinPoint]]: ...


class TidepoolClient:
    """Real client shell — raises until Tidepool credentials are wired."""

    async def fetch(self, start: date, end: date) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
        settings = get_settings()
        if not getattr(settings, "tidepool_email", None):
            raise IntegrationNotConfigured("Tidepool credentials not configured")
        raise NotImplementedError  # pragma: no cover


@dataclass
class DiabetesSyncResult:
    glucose: int
    insulin: int
    pump_uploaded: bool


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


async def sync_diabetes(
    session: AsyncSession, provider: TidepoolProvider, start: date, end: date
) -> DiabetesSyncResult:
    glucose, insulin = await provider.fetch(start, end)
    lo, hi = _bounds(start, end)
    # Idempotent: clear the window, then insert the fresh pull.
    await session.execute(
        delete(GlucoseReading).where(GlucoseReading.ts >= lo, GlucoseReading.ts <= hi)
    )
    await session.execute(delete(InsulinEvent).where(InsulinEvent.ts >= lo, InsulinEvent.ts <= hi))
    for g in glucose:
        session.add(GlucoseReading(ts=g.ts, mmol_l=g.mmol_l))
    for i in insulin:
        session.add(InsulinEvent(ts=i.ts, kind=i.kind, units=i.units, carbs_g=i.carbs_g))
    await session.commit()
    return DiabetesSyncResult(
        glucose=len(glucose), insulin=len(insulin), pump_uploaded=len(insulin) > 0
    )


async def glucose_summary(
    session: AsyncSession, start: date, end: date
) -> dict[str, float | int | None]:
    lo, hi = _bounds(start, end)
    values = (
        (
            await session.execute(
                select(GlucoseReading.mmol_l).where(
                    GlucoseReading.ts >= lo, GlucoseReading.ts <= hi
                )
            )
        )
        .scalars()
        .all()
    )
    if not values:
        return {"average": None, "time_in_range_pct": None, "count": 0}
    in_range = [v for v in values if TIR_LOW <= v <= TIR_HIGH]
    return {
        "average": round(sum(values) / len(values), 1),
        "time_in_range_pct": round(100 * len(in_range) / len(values), 1),
        "count": len(values),
    }


async def insulin_count(session: AsyncSession, start: date, end: date) -> int:
    lo, hi = _bounds(start, end)
    rows = (
        (
            await session.execute(
                select(InsulinEvent.id).where(InsulinEvent.ts >= lo, InsulinEvent.ts <= hi)
            )
        )
        .scalars()
        .all()
    )
    return len(rows)
