"""Graph data for the diabetes screen: daily BG trace + IOB + meal/workout overlays,
and per-day average trends over a week / month.

Glucose/insulin timestamps are stored UTC; everything here is bucketed and plotted in
the user's configured timezone so "today's curve" lines up with the user's clock.
The x-axis unit for the daily view is *minutes since local midnight* (0–1440), which
the frontend renders directly.

IOB is a MODEL, not a pump-reported figure: a standard rapid-acting exponential
insulin-activity curve (peak ~75 min, DIA 5 h), summed over bolus events. Basal is
excluded, as is conventional for "insulin on board".
"""

import math
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GlucoseReading, InsulinEvent, Meal, MealCheck, Session, SetEntry

# Standard CGM time-in-range band (mmol/L).
TIR_LOW = 3.9
TIR_HIGH = 10.0

# Rapid-acting insulin action model (minutes). Tandem Control-IQ defaults to ~5 h DIA.
_PEAK_MIN = 75.0
_DIA_MIN = 300.0
_GRID_MIN = 5  # IOB sample resolution across the day


def _iob_fraction(t_min: float, peak: float = _PEAK_MIN, dia: float = _DIA_MIN) -> float:
    """Fraction of a bolus still 'on board' t minutes after delivery (exponential model)."""
    if t_min <= 0:
        return 1.0 if t_min == 0 else 0.0
    if t_min >= dia:
        return 0.0
    tau = peak * (1 - peak / dia) / (1 - 2 * peak / dia)
    a = 2 * tau / dia
    s = 1 / (1 - a + (1 + a) * math.exp(-dia / tau))
    iob = 1 - s * (1 - a) * (
        (t_min**2 / (tau * dia * (1 - a)) - t_min / tau - 1) * math.exp(-t_min / tau) + 1
    )
    return max(0.0, min(1.0, iob))


def _as_utc(dt: datetime) -> datetime:
    """Treat a naive datetime (sqlite) as UTC; pass aware datetimes (postgres) through."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _utc_window(local_start: datetime, local_end: datetime) -> tuple[datetime, datetime]:
    """Naive-UTC query bounds (matches how timestamps are stored), from local bounds."""
    return (
        local_start.astimezone(UTC).replace(tzinfo=None),
        local_end.astimezone(UTC).replace(tzinfo=None),
    )


@dataclass
class _Bolus:
    ts_utc: datetime
    units: float


async def daily_series(
    session: AsyncSession, day: date, tz: ZoneInfo, user_id: int
) -> dict[str, object]:
    """Glucose trace, IOB line, and meal/workout markers for one local day."""
    local_start = datetime.combine(day, time.min, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    lo, hi = _utc_window(local_start, local_end)

    grows = (
        await session.execute(
            select(GlucoseReading.ts, GlucoseReading.mmol_l)
            .where(
                GlucoseReading.ts >= lo, GlucoseReading.ts < hi, GlucoseReading.user_id == user_id
            )
            .order_by(GlucoseReading.ts)
        )
    ).all()
    # Boluses up to one DIA before the day start still contribute IOB at midnight.
    blo, _ = _utc_window(local_start - timedelta(minutes=_DIA_MIN), local_end)
    brows = (
        await session.execute(
            select(InsulinEvent.ts, InsulinEvent.units).where(
                InsulinEvent.kind == "bolus",
                InsulinEvent.ts >= blo,
                InsulinEvent.ts < hi,
                InsulinEvent.user_id == user_id,
            )
        )
    ).all()
    boluses = [_Bolus(_as_utc(ts), units) for ts, units in brows]

    def _local_min(dt: datetime) -> int:
        local = _as_utc(dt).astimezone(tz)
        return local.hour * 60 + local.minute

    glucose_by_min: dict[int, float] = {}
    for ts, mmol in grows:
        glucose_by_min[_local_min(ts)] = mmol

    def _iob_at(minute: int) -> float:
        t_utc = (local_start + timedelta(minutes=minute)).astimezone(UTC)
        total = 0.0
        for b in boluses:
            dt_min = (t_utc - b.ts_utc).total_seconds() / 60
            if 0 <= dt_min < _DIA_MIN:
                total += b.units * _iob_fraction(dt_min)
        return total

    # Union of glucose sample minutes and a regular IOB grid → one tidy series.
    grid = sorted(set(glucose_by_min) | set(range(0, 1440, _GRID_MIN)))
    points = [
        {"min": m, "mmol_l": glucose_by_min.get(m), "iob": round(_iob_at(m), 2)} for m in grid
    ]

    meal_rows = (
        await session.execute(
            select(MealCheck.checked_at, Meal.name, Meal.carbs_g)
            .join(Meal, Meal.id == MealCheck.meal_id)
            .where(
                MealCheck.date == day,
                MealCheck.eaten.is_(True),
                MealCheck.checked_at.is_not(None),
                MealCheck.user_id == user_id,
            )
        )
    ).all()
    meals = [
        {"min": _local_min(checked_at), "name": name, "carbs_g": carbs}
        for checked_at, name, carbs in meal_rows
    ]

    set_times = (
        (
            await session.execute(
                select(SetEntry.created_at)
                .join(Session, Session.id == SetEntry.session_id)
                .where(Session.date == day, Session.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    workouts: list[dict[str, object]] = []
    if set_times:
        mins = [_local_min(t) for t in set_times]
        workouts.append({"start_min": min(mins), "end_min": max(mins), "label": "Workout"})

    return {
        "range": "day",
        "date": day.isoformat(),
        "points": points,
        "meals": meals,
        "workouts": workouts,
        "tir_low": TIR_LOW,
        "tir_high": TIR_HIGH,
    }


async def trend_series(
    session: AsyncSession, start: date, end: date, tz: ZoneInfo, user_id: int
) -> dict[str, object]:
    """Per-day average BG and time-in-range across [start, end] (inclusive), local days."""
    local_start = datetime.combine(start, time.min, tzinfo=tz)
    local_end = datetime.combine(end, time.min, tzinfo=tz) + timedelta(days=1)
    lo, hi = _utc_window(local_start, local_end)

    rows = (
        await session.execute(
            select(GlucoseReading.ts, GlucoseReading.mmol_l).where(
                GlucoseReading.ts >= lo, GlucoseReading.ts < hi, GlucoseReading.user_id == user_id
            )
        )
    ).all()

    buckets: dict[date, list[float]] = {}
    for ts, mmol in rows:
        d = _as_utc(ts).astimezone(tz).date()
        buckets.setdefault(d, []).append(mmol)

    daily: list[dict[str, object]] = []
    cursor = start
    while cursor <= end:
        vals = buckets.get(cursor, [])
        if vals:
            in_range = [v for v in vals if TIR_LOW <= v <= TIR_HIGH]
            daily.append(
                {
                    "date": cursor.isoformat(),
                    "avg": round(sum(vals) / len(vals), 1),
                    "tir_pct": round(100 * len(in_range) / len(vals), 1),
                    "count": len(vals),
                }
            )
        else:
            daily.append({"date": cursor.isoformat(), "avg": None, "tir_pct": None, "count": 0})
        cursor += timedelta(days=1)

    return {
        "range": "week" if (end - start).days < 14 else "month",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "daily": daily,
        "tir_low": TIR_LOW,
        "tir_high": TIR_HIGH,
    }
