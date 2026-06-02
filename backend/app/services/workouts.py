"""Workout logging helpers, incl. the progressive-overload 'last week' column.

Last-week rule (LOCKED): show ONLY the heaviest weight from the most recent PRIOR session
(strictly before the reference date — today's own sets never count). Bodyweight exercises
(no weight on any set that day) show "BW". No prior history shows "—".
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise, Session, SetEntry

NO_HISTORY = "—"
BODYWEIGHT = "BW"


def _format_weight(weight: float) -> str:
    text = str(int(weight)) if weight == int(weight) else f"{weight:g}"
    return f"{text} kg"


def set_display(weight: str | None, reps: str | None) -> str:
    left = BODYWEIGHT if weight in (None, "") else f"{weight} kg"
    return f"{left} × {reps}" if reps not in (None, "") else left


async def get_or_create_exercise(session: AsyncSession, slug: str) -> Exercise:
    ex = await session.scalar(select(Exercise).where(Exercise.slug == slug))
    if ex is None:
        ex = Exercise(slug=slug, name=slug.replace("-", " ").title())
        session.add(ex)
        await session.flush()
    return ex


def _to_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


async def last_week_display(session: AsyncSession, exercise_slug: str, before: date) -> str:
    ex = await session.scalar(select(Exercise).where(Exercise.slug == exercise_slug))
    if ex is None:
        return NO_HISTORY

    most_recent = await session.scalar(
        select(Session.date)
        .join(SetEntry, SetEntry.session_id == Session.id)
        .where(SetEntry.exercise_id == ex.id, Session.date < before)
        .order_by(Session.date.desc())
        .limit(1)
    )
    if most_recent is None:
        return NO_HISTORY

    weights_raw = (
        (
            await session.execute(
                select(SetEntry.weight)
                .join(Session, SetEntry.session_id == Session.id)
                .where(SetEntry.exercise_id == ex.id, Session.date == most_recent)
            )
        )
        .scalars()
        .all()
    )

    weights = [w for w in (_to_float(x) for x in weights_raw) if w is not None]
    if not weights:
        return BODYWEIGHT
    return _format_weight(max(weights))
