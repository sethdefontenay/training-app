"""Assemble the weekly check-in over a rolling 7-day window.

Pulls measurements, the four daily /10s (values + average over LOGGED days only —
missing days are never counted as zero), and light adherence context. Glucose/insulin
are deliberately excluded: they are Seth's own record, not part of the PT package.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyWellbeing, Measurement, Session

METRICS = ("energy", "motivation", "stress", "hunger")


def window_for(start_on: date) -> tuple[date, date]:
    """The 7 days ending on start_on (inclusive)."""
    return start_on - timedelta(days=6), start_on


async def metric_summaries(
    session: AsyncSession, window_start: date, window_end: date
) -> dict[str, dict[str, object]]:
    rows = (
        (
            await session.execute(
                select(DailyWellbeing)
                .where(DailyWellbeing.date >= window_start, DailyWellbeing.date <= window_end)
                .order_by(DailyWellbeing.date)
            )
        )
        .scalars()
        .all()
    )
    out: dict[str, dict[str, object]] = {}
    for metric in METRICS:
        values = [
            {"date": r.date.isoformat(), "value": getattr(r, metric)}
            for r in rows
            if getattr(r, metric) is not None
        ]
        nums = [v["value"] for v in values]
        average = round(sum(nums) / len(nums), 1) if nums else None
        out[metric] = {"values": values, "average": average}
    return out


async def latest_measurement(
    session: AsyncSession, window_start: date, window_end: date
) -> Measurement | None:
    row: Measurement | None = await session.scalar(
        select(Measurement)
        .where(Measurement.date >= window_start, Measurement.date <= window_end)
        .order_by(Measurement.date.desc())
        .limit(1)
    )
    return row


async def sessions_logged(session: AsyncSession, window_start: date, window_end: date) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.date >= window_start, Session.date <= window_end)
    )
    return count or 0
