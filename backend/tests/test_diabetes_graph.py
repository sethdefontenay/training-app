"""diabetes_data.feature: BG trace + IOB line + meal/workout overlays, and weekly trend.

Timestamps are seeded in the configured local timezone (converted to the stored
naive-UTC form) so the day-bucketing assertions are deterministic regardless of where
CI runs.
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import Exercise, GlucoseReading, InsulinEvent, MealCheck, Session, SetEntry, User
from tests.test_daily import _seed_plan

DAY = date(2026, 5, 25)
_TZ = ZoneInfo(get_settings().timezone)


async def _uid(session: AsyncSession) -> int:
    return int(await session.scalar(select(User.id).order_by(User.id).limit(1)))


def _utc(day: date, hour: int, minute: int = 0) -> datetime:
    """A local wall-clock time on `day`, as the stored naive-UTC value."""
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=_TZ)
    return local.astimezone(UTC).replace(tzinfo=None)


async def test_daily_iob_curve_from_bolus(auth_client: AsyncClient, session: AsyncSession) -> None:
    # 5 U bolus at local noon, glucose 8.0 at 12:05.
    uid = await _uid(session)
    session.add(InsulinEvent(user_id=uid, ts=_utc(DAY, 12), kind="bolus", units=5.0))
    session.add(GlucoseReading(user_id=uid, ts=_utc(DAY, 12, 5), mmol_l=8.0))
    await session.commit()

    body = (
        await auth_client.get(
            "/api/v1/diabetes/graph", params={"range": "day", "date": DAY.isoformat()}
        )
    ).json()
    assert body["range"] == "day"
    pts = {p["min"]: p for p in body["points"]}

    # IOB peaks at the bolus (~all 5 U on board) and is fully decayed one DIA (5h) later.
    assert pts[720]["iob"] >= 4.9
    assert pts[1020]["iob"] == 0.0  # 17:00, 5h after the bolus
    # Glucose value is plotted at its local minute.
    assert pts[725]["mmol_l"] == 8.0


async def test_daily_meal_and_workout_markers(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    meal = await _seed_plan(session)
    uid = await _uid(session)
    session.add(
        MealCheck(user_id=uid, date=DAY, meal_id=meal.id, eaten=True, checked_at=_utc(DAY, 12, 30))
    )
    sess = Session(user_id=uid, date=DAY, weekday=DAY.strftime("%A"))
    session.add(sess)
    await session.flush()
    ex = Exercise(slug="squat", name="Squat")
    session.add(ex)
    await session.flush()
    session.add(
        SetEntry(
            session_id=sess.id,
            exercise_id=ex.id,
            set_index=1,
            reps="10",
            weight="60",
            created_at=_utc(DAY, 16),
        )
    )
    await session.commit()

    body = (
        await auth_client.get(
            "/api/v1/diabetes/graph", params={"range": "day", "date": DAY.isoformat()}
        )
    ).json()
    assert len(body["meals"]) == 1
    assert body["meals"][0]["min"] == 12 * 60 + 30
    assert body["meals"][0]["carbs_g"] == 74
    assert len(body["workouts"]) == 1
    assert body["workouts"][0]["start_min"] == 16 * 60


async def test_weekly_trend_daily_averages(auth_client: AsyncClient, session: AsyncSession) -> None:
    uid = await _uid(session)
    session.add(GlucoseReading(user_id=uid, ts=_utc(DAY, 9), mmol_l=5.0))
    session.add(GlucoseReading(user_id=uid, ts=_utc(DAY, 10), mmol_l=11.0))  # avg 8.0, one in-range
    await session.commit()

    body = (
        await auth_client.get(
            "/api/v1/diabetes/graph", params={"range": "week", "date": DAY.isoformat()}
        )
    ).json()
    assert body["range"] == "week"
    assert len(body["daily"]) == 7
    today = next(d for d in body["daily"] if d["date"] == DAY.isoformat())
    assert today["avg"] == 8.0
    assert today["tir_pct"] == 50.0
    assert today["count"] == 2
