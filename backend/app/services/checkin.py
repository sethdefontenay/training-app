"""Assemble the weekly check-in over a rolling 7-day window.

Pulls measurements, the four daily /10s (values + average over LOGGED days only —
missing days are never counted as zero), and light adherence context. Glucose/insulin
are deliberately excluded: they are Seth's own record, not part of the PT package.
"""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyWellbeing, Measurement, Session, SleepNight, StepsDay

METRICS = ("energy", "motivation", "stress", "hunger")
MEASUREMENT_FIELDS = (
    "waist_cm",
    "tummy_cm",
    "bum_cm",
    "right_thigh_cm",
    "left_thigh_cm",
    "weight_kg",
)


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


async def latest_per_metric(session: AsyncSession, on_or_before: date) -> dict[str, float | None]:
    """Most recent recorded value for each body metric (may be from different dates).

    One query (was one per field): pull rows newest-first and keep the first non-null
    value seen for each field. A single user has few measurement rows, so scanning them
    is far cheaper than six round-trips.
    """
    out: dict[str, float | None] = {f: None for f in MEASUREMENT_FIELDS}
    remaining = set(MEASUREMENT_FIELDS)
    rows = (
        (
            await session.execute(
                select(Measurement)
                .where(Measurement.date <= on_or_before)
                .order_by(Measurement.date.desc())
            )
        )
        .scalars()
        .all()
    )
    for row in rows:
        for field in tuple(remaining):
            value = getattr(row, field)
            if value is not None:
                out[field] = value
                remaining.discard(field)
        if not remaining:
            break
    return out


async def steps_average(
    session: AsyncSession, window_start: date, window_end: date
) -> float | None:
    avg = await session.scalar(
        select(func.avg(StepsDay.steps)).where(
            StepsDay.date >= window_start, StepsDay.date <= window_end
        )
    )
    return round(float(avg)) if avg is not None else None


async def sleep_summary(
    session: AsyncSession, window_start: date, window_end: date
) -> dict[str, float | int | None]:
    row = (
        await session.execute(
            select(
                func.avg(SleepNight.efficiency),
                func.avg(SleepNight.asleep_min),
                func.count(SleepNight.id),
            ).where(SleepNight.date >= window_start, SleepNight.date <= window_end)
        )
    ).one()
    avg_eff, avg_asleep, nights = row
    return {
        "avg_efficiency": round(float(avg_eff), 1) if avg_eff is not None else None,
        "avg_asleep_min": round(float(avg_asleep)) if avg_asleep is not None else None,
        "nights": int(nights or 0),
    }


async def sessions_logged(session: AsyncSession, window_start: date, window_end: date) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(Session)
        .where(Session.date >= window_start, Session.date <= window_end)
    )
    return count or 0
