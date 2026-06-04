"""Workout logging helpers, incl. the progressive-overload 'last week' column.

Last-week rule (LOCKED): show ONLY the heaviest weight from the most recent PRIOR session
(strictly before the reference date — today's own sets never count). Bodyweight exercises
(no weight on any set that day) show "BW". No prior history shows "—".
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Exercise, Session, SetEntry


async def progression(session: AsyncSession, slug: str) -> list[dict[str, object]]:
    """Per-session-date top display, oldest to newest. Weighted -> heaviest 'N kg';
    bodyweight -> best 'N reps'."""
    ex = await session.scalar(select(Exercise).where(Exercise.slug == slug))
    if ex is None:
        return []
    rows = (
        await session.execute(
            select(Session.date, SetEntry.weight, SetEntry.reps)
            .join(SetEntry, SetEntry.session_id == Session.id)
            .where(SetEntry.exercise_id == ex.id)
            .order_by(Session.date)
        )
    ).all()
    by_date: dict[date, list[tuple[str | None, str | None]]] = {}
    for day, weight, reps in rows:
        by_date.setdefault(day, []).append((weight, reps))

    points: list[dict[str, object]] = []
    for day in sorted(by_date):
        weights = [f for f in (_to_float(w) for w, _ in by_date[day]) if f is not None]
        if weights:
            display = _format_weight(max(weights))
        else:
            reps_vals = [int(r) for _, r in by_date[day] if r and r.isdigit()]
            display = f"{max(reps_vals)} reps" if reps_vals else NO_HISTORY
        points.append({"date": day, "display": display})
    return points


NO_HISTORY = "—"
BODYWEIGHT = "BW"


async def list_sessions(session: AsyncSession) -> list[dict[str, object]]:
    """Logged workout sessions (those with sets), most recent first, grouped by exercise."""
    from sqlalchemy.orm import selectinload

    rows = (
        await session.scalars(
            select(Session)
            .options(selectinload(Session.sets).selectinload(SetEntry.exercise))
            .order_by(Session.date.desc())
        )
    ).all()
    out: list[dict[str, object]] = []
    for s in rows:
        if not s.sets:
            continue  # rest/empty days aren't workouts
        by_ex: dict[tuple[str, str], list[str]] = {}
        for e in sorted(s.sets, key=lambda x: (x.exercise_id, x.set_index)):
            by_ex.setdefault((e.exercise.slug, e.exercise.name), []).append(
                set_display(e.weight, e.reps)
            )
        out.append(
            {
                "id": s.id,
                "date": s.date,
                "weekday": s.weekday,
                "exercises": [
                    {"slug": slug, "name": name, "sets": sets}
                    for (slug, name), sets in by_ex.items()
                ],
            }
        )
    return out


async def progress_series(
    session: AsyncSession, slug: str
) -> tuple[str, str, list[dict[str, object]]] | None:
    """For an exercise, the top set per workout day over time (oldest → newest).

    Returns (name, metric, points). 'metric' is "weight" if any day has a weighted set,
    else "reps" (bodyweight progression). Each point carries the heaviest weight and the
    reps at that set (ties on weight broken by most reps), matching the locked rule.
    """
    ex = await session.scalar(select(Exercise).where(Exercise.slug == slug))
    if ex is None:
        return None
    rows = (
        await session.execute(
            select(Session.date, SetEntry.weight, SetEntry.reps)
            .join(SetEntry, SetEntry.session_id == Session.id)
            .where(SetEntry.exercise_id == ex.id)
            .order_by(Session.date)
        )
    ).all()

    by_date: dict[date, list[tuple[str | None, str | None]]] = {}
    for day, weight, reps in rows:
        by_date.setdefault(day, []).append((weight, reps))

    points: list[dict[str, object]] = []
    any_weight = False
    for day in sorted(by_date):
        sets = by_date[day]
        # Top set: max weight, ties broken by most reps.
        best = max(sets, key=lambda wr: (_to_float(wr[0]) or -1.0, _reps_int(wr[1]) or -1))
        weight = _to_float(best[0])
        reps = _reps_int(best[1])
        if weight is not None:
            any_weight = True
            display = set_display(best[0], best[1])
        else:
            best_reps = max((_reps_int(r) or 0 for _, r in sets), default=0)
            reps = best_reps or None
            display = f"{best_reps} reps" if best_reps else BODYWEIGHT
        points.append({"date": day, "weight": weight, "reps": reps, "display": display})

    return ex.name, ("weight" if any_weight else "reps"), points


def _reps_int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None


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
