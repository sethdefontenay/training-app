"""Sleep analysis: per-night stage timeline (hypnogram) and weekly trends."""

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SleepNight


async def latest_night_date(session: AsyncSession) -> date | None:
    d: date | None = await session.scalar(
        select(SleepNight.date)
        .where(SleepNight.asleep_min.is_not(None))
        .order_by(SleepNight.date.desc())
        .limit(1)
    )
    return d


async def night_view(session: AsyncSession, day: date) -> dict[str, object]:
    """One night: totals, efficiency, and stage segments as minutes-since-first-stage."""
    row = await session.scalar(select(SleepNight).where(SleepNight.date == day))
    if row is None:
        return {"date": day.isoformat(), "found": False}

    segments: list[dict[str, object]] = []
    if row.stages:
        starts = [datetime.fromisoformat(s["start"]) for s in row.stages]
        t0 = min(starts)
        for s in row.stages:
            st = datetime.fromisoformat(s["start"])
            en = datetime.fromisoformat(s["end"])
            segments.append(
                {
                    "type": s["type"],
                    "start_min": round((st - t0).total_seconds() / 60, 1),
                    "end_min": round((en - t0).total_seconds() / 60, 1),
                    "start_hm": st.strftime("%H:%M"),
                    "end_hm": en.strftime("%H:%M"),
                }
            )

    return {
        "date": row.date.isoformat(),
        "found": True,
        "bedtime": row.bedtime,
        "wake_time": row.wake_time,
        "asleep_min": row.asleep_min,
        "in_bed_min": row.in_bed_min,
        "awake_min": row.awake_min,
        "light_min": row.light_min,
        "deep_min": row.deep_min,
        "rem_min": row.rem_min,
        "efficiency": row.efficiency,
        "segments": segments,
    }


async def trend(session: AsyncSession, start: date, end: date) -> dict[str, object]:
    """Per-night stage breakdown + averages across [start, end] (inclusive)."""
    rows = (
        (
            await session.execute(
                select(SleepNight)
                .where(SleepNight.date >= start, SleepNight.date <= end)
                .order_by(SleepNight.date)
            )
        )
        .scalars()
        .all()
    )
    nights = [
        {
            "date": r.date.isoformat(),
            "asleep_min": r.asleep_min,
            "light_min": r.light_min,
            "deep_min": r.deep_min,
            "rem_min": r.rem_min,
            "awake_min": r.awake_min,
            "efficiency": r.efficiency,
        }
        for r in rows
    ]

    def _avg(key: str) -> float | None:
        vals = [v for v in (getattr(r, key) for r in rows) if v is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "nights": nights,
        "averages": {
            "asleep_min": _avg("asleep_min"),
            "efficiency": _avg("efficiency"),
            "light_min": _avg("light_min"),
            "deep_min": _avg("deep_min"),
            "rem_min": _avg("rem_min"),
            "count": len(rows),
        },
    }
