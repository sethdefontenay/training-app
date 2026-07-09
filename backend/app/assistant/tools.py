"""The assistant's capability layer: read + write/ingest tools over the user's data.

One registry, reused by the in-app agent (executed in-process) and — later — by the
MCP server. Every handler is async (session, args) -> JSON-serialisable result. Reads
reuse existing services; writes go through the same models the REST API uses. Dates are
in the user's local timezone.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clock import local_now, local_today
from app.config import get_settings
from app.integrations.tidepool import glucose_summary, insulin_count
from app.models import (
    DailyWellbeing,
    GlucoseReading,
    MealCheck,
    Measurement,
    Plan,
    Prescription,
    ProgramExercise,
    Session,
    SetEntry,
    SleepNight,
    StepsDay,
    TrainingDay,
    User,
    WeekdayProgram,
    WorkoutProgram,
)
from app.schemas.tracking import _MEASUREMENT_FIELDS
from app.services.daily import resolve_day
from app.services.programs import import_training_days, list_programs, load_program
from app.services.workouts import get_or_create_exercise, list_sessions, progress_series

JSON = dict[str, object]
Handler = Callable[[AsyncSession, JSON, int], Awaitable[object]]


@dataclass
class Tool:
    name: str
    description: str
    input_schema: JSON
    handler: Handler
    writes: bool = False


_TOOLS: list[Tool] = []


def tool(
    name: str, description: str, schema: JSON, *, writes: bool = False
) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        _TOOLS.append(Tool(name, description, schema, fn, writes))
        return fn

    return deco


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def _day(args: JSON, key: str = "date") -> date:
    v = args.get(key)
    return date.fromisoformat(str(v)) if v else local_today()


_DATE_PROP: JSON = {"type": "string", "description": "Date YYYY-MM-DD (defaults to today)"}
_EMPTY: JSON = {"type": "object", "properties": {}}


# --- reads ---


@tool(
    "get_today",
    "The full daily view for a date: plan workout, meals (+ eaten), "
    "wellbeing scores, steps. Use for 'what's on today', adherence, etc.",
    {"type": "object", "properties": {"date": _DATE_PROP}},
)
async def _get_today(session: AsyncSession, args: JSON, user_id: int) -> object:
    return (await resolve_day(session, _day(args), user_id)).model_dump(mode="json")


@tool(
    "get_plan",
    "The current training plan: training days with exercises, daily "
    "targets (calories/macros/steps/water), phase, and days since it started.",
    _EMPTY,
)
async def _get_plan(session: AsyncSession, args: JSON, user_id: int) -> object:
    plan = await session.scalar(
        select(Plan)
        .where(Plan.is_current.is_(True), Plan.user_id == user_id)
        .options(
            selectinload(Plan.training_days)
            .selectinload(TrainingDay.prescriptions)
            .selectinload(Prescription.exercise)
        )
    )
    if plan is None:
        return {"plan": None}
    return {
        "phase": plan.phase,
        "start_date": plan.start_date.isoformat(),
        "days_since_start": (local_today() - plan.start_date).days,
        "targets": {
            "daily_calories": plan.daily_calories,
            "daily_protein_g": plan.daily_protein_g,
            "daily_carbs_g": plan.daily_carbs_g,
            "daily_fat_g": plan.daily_fat_g,
            "steps_target": plan.steps_target,
        },
        "training_days": [
            {
                "label": td.label,
                "exercises": [
                    {
                        "slug": p.exercise.slug,
                        "name": p.exercise.name,
                        "sets_x_reps": p.sets_x_reps,
                        "prescribed_weight": p.prescribed_weight,
                    }
                    for p in sorted(td.prescriptions, key=lambda x: x.order)
                ],
            }
            for td in sorted(plan.training_days, key=lambda x: x.order)
        ],
    }


@tool(
    "get_glucose_summary",
    "Glucose average, time-in-range %, reading count and insulin "
    "event count over the last N days (default 7).",
    {"type": "object", "properties": {"days": {"type": "integer", "description": "default 7"}}},
)
async def _get_glucose_summary(session: AsyncSession, args: JSON, user_id: int) -> object:
    days = int(str(args.get("days", 7)))
    end = local_today()
    start = end - timedelta(days=days - 1)
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "glucose": await glucose_summary(session, start, end, user_id),
        "insulin_events": await insulin_count(session, start, end, user_id),
    }


@tool(
    "get_glucose_by_hour",
    "Hourly average glucose (mmol/L) for a single day, in local "
    "time — useful for 'what was my BG around lunch'.",
    {"type": "object", "properties": {"date": _DATE_PROP}},
)
async def _get_glucose_by_hour(session: AsyncSession, args: JSON, user_id: int) -> object:
    day = _day(args)
    tz = _tz()
    lo = datetime.combine(day, datetime.min.time(), tzinfo=tz).astimezone(ZoneInfo("UTC"))
    hi = lo + timedelta(days=1)
    rows = (
        await session.execute(
            select(GlucoseReading.ts, GlucoseReading.mmol_l).where(
                GlucoseReading.ts >= lo.replace(tzinfo=None),
                GlucoseReading.ts < hi.replace(tzinfo=None),
                GlucoseReading.user_id == user_id,
            )
        )
    ).all()
    buckets: dict[int, list[float]] = {}
    for ts, mmol in rows:
        local_h = (
            (ts.replace(tzinfo=ZoneInfo("UTC")) if ts.tzinfo is None else ts).astimezone(tz).hour
        )
        buckets.setdefault(local_h, []).append(mmol)
    return {
        "date": day.isoformat(),
        "hourly": [
            {"hour": h, "avg_mmol_l": round(sum(v) / len(v), 1), "n": len(v)}
            for h, v in sorted(buckets.items())
        ],
    }


@tool(
    "get_workout_history",
    "Logged workout sessions (most recent first), each with its exercises and sets.",
    _EMPTY,
)
async def _get_workout_history(session: AsyncSession, args: JSON, user_id: int) -> object:
    return await list_sessions(session, user_id)


@tool(
    "get_exercise_progress",
    "An exercise's top set per workout day over time (heaviest "
    "weight, or reps for bodyweight). Use the exercise slug from get_plan.",
    {"type": "object", "properties": {"slug": {"type": "string"}}, "required": ["slug"]},
)
async def _get_exercise_progress(session: AsyncSession, args: JSON, user_id: int) -> object:
    result = await progress_series(session, str(args["slug"]), user_id)
    if result is None:
        return {"error": "unknown exercise slug"}
    name, metric, points = result
    return {"name": name, "metric": metric, "points": points}


@tool(
    "get_measurements",
    "Recent body measurements (waist, weight, etc.), newest first.",
    {"type": "object", "properties": {"limit": {"type": "integer", "description": "default 10"}}},
)
async def _get_measurements(session: AsyncSession, args: JSON, user_id: int) -> object:
    limit = int(str(args.get("limit", 10)))
    rows = (
        await session.scalars(
            select(Measurement)
            .where(Measurement.user_id == user_id)
            .order_by(Measurement.date.desc())
            .limit(limit)
        )
    ).all()
    return [
        {"date": r.date.isoformat(), **{f: getattr(r, f) for f in _MEASUREMENT_FIELDS}}
        for r in rows
    ]


@tool(
    "get_steps_sleep",
    "Daily steps and sleep (asleep minutes, efficiency) over the last N days (default 7).",
    {"type": "object", "properties": {"days": {"type": "integer", "description": "default 7"}}},
)
async def _get_steps_sleep(session: AsyncSession, args: JSON, user_id: int) -> object:
    days = int(str(args.get("days", 7)))
    end = local_today()
    start = end - timedelta(days=days - 1)
    steps = (
        await session.execute(
            select(StepsDay.date, StepsDay.steps, StepsDay.target_steps)
            .where(StepsDay.date >= start, StepsDay.date <= end, StepsDay.user_id == user_id)
            .order_by(StepsDay.date)
        )
    ).all()
    sleep = (
        await session.execute(
            select(SleepNight.date, SleepNight.asleep_min, SleepNight.efficiency)
            .where(SleepNight.date >= start, SleepNight.date <= end, SleepNight.user_id == user_id)
            .order_by(SleepNight.date)
        )
    ).all()
    return {
        "steps": [{"date": d.isoformat(), "steps": s, "target": t} for d, s, t in steps],
        "sleep": [{"date": d.isoformat(), "asleep_min": a, "efficiency": e} for d, a, e in sleep],
    }


# --- writes / ingestion ---


@tool(
    "log_set",
    "Log a workout set on a date. Creates the day's session if needed. "
    "weight is a string (kg) or empty for bodyweight.",
    {
        "type": "object",
        "properties": {
            "date": _DATE_PROP,
            "exercise_slug": {"type": "string"},
            "reps": {"type": "string"},
            "weight": {"type": "string"},
        },
        "required": ["exercise_slug", "reps"],
    },
    writes=True,
)
async def _log_set(session: AsyncSession, args: JSON, user_id: int) -> object:
    day = _day(args)
    sess = await session.scalar(
        select(Session).where(Session.date == day, Session.user_id == user_id)
    )
    if sess is None:
        sess = Session(user_id=user_id, date=day, weekday=day.strftime("%A"))
        session.add(sess)
        await session.flush()
    ex = await get_or_create_exercise(session, str(args["exercise_slug"]), user_id)
    count = len(
        (
            await session.execute(
                select(SetEntry.id).where(
                    SetEntry.session_id == sess.id, SetEntry.exercise_id == ex.id
                )
            )
        ).all()
    )
    entry = SetEntry(
        session_id=sess.id,
        exercise_id=ex.id,
        set_index=count + 1,
        reps=str(args.get("reps") or ""),
        weight=str(args.get("weight") or "") or None,
    )
    session.add(entry)
    await session.commit()
    return {
        "logged": {
            "date": day.isoformat(),
            "exercise": ex.name,
            "set_index": entry.set_index,
            "reps": entry.reps,
            "weight": entry.weight,
        }
    }


@tool(
    "check_meal",
    "Mark a planned meal as eaten (or not) on a date. meal_id comes from get_today.",
    {
        "type": "object",
        "properties": {
            "date": _DATE_PROP,
            "meal_id": {"type": "integer"},
            "eaten": {"type": "boolean", "description": "default true"},
        },
        "required": ["meal_id"],
    },
    writes=True,
)
async def _check_meal(session: AsyncSession, args: JSON, user_id: int) -> object:
    day = _day(args)
    meal_id = int(str(args["meal_id"]))
    eaten = bool(args.get("eaten", True))
    row = await session.scalar(
        select(MealCheck).where(
            MealCheck.date == day, MealCheck.meal_id == meal_id, MealCheck.user_id == user_id
        )
    )
    if eaten:
        if row is None:
            session.add(
                MealCheck(
                    user_id=user_id, date=day, meal_id=meal_id, eaten=True, checked_at=local_now()
                )
            )
        else:
            row.eaten, row.checked_at = True, local_now()
    elif row is not None:
        await session.delete(row)
    await session.commit()
    return {"date": day.isoformat(), "meal_id": meal_id, "eaten": eaten}


@tool(
    "set_wellbeing",
    "Set wellbeing scores (1-10) for a date: any of energy, motivation, stress, hunger.",
    {
        "type": "object",
        "properties": {
            "date": _DATE_PROP,
            "energy": {"type": "integer"},
            "motivation": {"type": "integer"},
            "stress": {"type": "integer"},
            "hunger": {"type": "integer"},
        },
    },
    writes=True,
)
async def _set_wellbeing(session: AsyncSession, args: JSON, user_id: int) -> object:
    day = _day(args)
    row = await session.scalar(
        select(DailyWellbeing).where(DailyWellbeing.date == day, DailyWellbeing.user_id == user_id)
    )
    if row is None:
        row = DailyWellbeing(user_id=user_id, date=day)
        session.add(row)
    for f in ("energy", "motivation", "stress", "hunger"):
        if args.get(f) is not None:
            setattr(row, f, int(str(args[f])))
    await session.commit()
    return {
        "date": day.isoformat(),
        "energy": row.energy,
        "motivation": row.motivation,
        "stress": row.stress,
        "hunger": row.hunger,
    }


@tool(
    "record_measurement",
    "Record body measurements for a date (cm / kg). Any subset of: "
    + ", ".join(_MEASUREMENT_FIELDS)
    + ".",
    {
        "type": "object",
        "properties": {"date": _DATE_PROP, **{f: {"type": "number"} for f in _MEASUREMENT_FIELDS}},
    },
    writes=True,
)
async def _record_measurement(session: AsyncSession, args: JSON, user_id: int) -> object:
    day = _day(args)
    row = await session.scalar(
        select(Measurement).where(Measurement.date == day, Measurement.user_id == user_id)
    )
    if row is None:
        row = Measurement(user_id=user_id, date=day)
        session.add(row)
    for f in _MEASUREMENT_FIELDS:
        if args.get(f) is not None:
            setattr(row, f, float(str(args[f])))
    await session.commit()
    return {"date": day.isoformat(), **{f: getattr(row, f) for f in _MEASUREMENT_FIELDS}}


# --- workout planner (the hub can build and modify programs) ---

_WEEKDAY_PROP: JSON = {"type": "string", "description": "monday..sunday"}


@tool(
    "list_programs",
    "List the user's workout programs (id, name, exercises) and their weekday->program "
    "schedule. Call this first to get program ids before modifying anything.",
    _EMPTY,
)
async def _list_programs(session: AsyncSession, args: JSON, user_id: int) -> object:
    user = await session.get(User, user_id)
    programs = await list_programs(session, user) if user else []
    sched = (
        (await session.execute(select(WeekdayProgram).where(WeekdayProgram.user_id == user_id)))
        .scalars()
        .all()
    )
    return {
        "programs": [
            {
                "id": p.id,
                "name": p.name,
                "exercises": [
                    {
                        "slug": pe.exercise.slug,
                        "name": pe.exercise.name,
                        "sets_x_reps": pe.sets_x_reps,
                        "prescribed_weight": pe.prescribed_weight,
                    }
                    for pe in sorted(p.exercises, key=lambda e: e.order)
                ],
            }
            for p in programs
        ],
        "schedule": [{"weekday": w.weekday, "program_id": w.program_id} for w in sched],
    }


@tool(
    "create_program",
    "Create a new empty workout program. Returns its id.",
    {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    writes=True,
)
async def _create_program(session: AsyncSession, args: JSON, user_id: int) -> object:
    p = WorkoutProgram(user_id=user_id, name=str(args["name"]))
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return {"created": {"id": p.id, "name": p.name}}


@tool(
    "add_program_exercise",
    "Add an exercise to a program. A new exercise_slug becomes the user's custom exercise. "
    "weight is optional (kg string).",
    {
        "type": "object",
        "properties": {
            "program_id": {"type": "integer"},
            "exercise_slug": {"type": "string"},
            "sets_x_reps": {"type": "string", "description": "e.g. '4 × 8'"},
            "prescribed_weight": {"type": "string"},
        },
        "required": ["program_id", "exercise_slug", "sets_x_reps"],
    },
    writes=True,
)
async def _add_program_exercise(session: AsyncSession, args: JSON, user_id: int) -> object:
    user = await session.get(User, user_id)
    program = await load_program(session, int(str(args["program_id"])), user) if user else None
    if program is None:
        return {"error": "unknown program_id"}
    ex = await get_or_create_exercise(session, str(args["exercise_slug"]), user_id)
    session.add(
        ProgramExercise(
            program_id=program.id,
            exercise_id=ex.id,
            sets_x_reps=str(args["sets_x_reps"]),
            prescribed_weight=(str(args.get("prescribed_weight")) or None)
            if args.get("prescribed_weight")
            else None,
            order=len(program.exercises),
        )
    )
    await session.commit()
    return {"added": {"program_id": program.id, "exercise": ex.name}}


@tool(
    "remove_program_exercise",
    "Remove an exercise (by slug) from a program.",
    {
        "type": "object",
        "properties": {"program_id": {"type": "integer"}, "exercise_slug": {"type": "string"}},
        "required": ["program_id", "exercise_slug"],
    },
    writes=True,
)
async def _remove_program_exercise(session: AsyncSession, args: JSON, user_id: int) -> object:
    user = await session.get(User, user_id)
    program = await load_program(session, int(str(args["program_id"])), user) if user else None
    if program is None:
        return {"error": "unknown program_id"}
    slug = str(args["exercise_slug"])
    match = next((pe for pe in program.exercises if pe.exercise.slug == slug), None)
    if match is None:
        return {"error": "exercise not in program"}
    await session.delete(match)
    await session.commit()
    return {"removed": {"program_id": program.id, "exercise_slug": slug}}


@tool(
    "assign_weekday_program",
    "Assign a program to a weekday (recurring, every week), or clear it with program_id=null "
    "so that weekday falls back to the PT plan.",
    {
        "type": "object",
        "properties": {"weekday": _WEEKDAY_PROP, "program_id": {"type": ["integer", "null"]}},
        "required": ["weekday"],
    },
    writes=True,
)
async def _assign_weekday_program(session: AsyncSession, args: JSON, user_id: int) -> object:
    weekday = str(args["weekday"]).lower()
    existing = await session.scalar(
        select(WeekdayProgram).where(
            WeekdayProgram.user_id == user_id, WeekdayProgram.weekday == weekday
        )
    )
    pid = args.get("program_id")
    if pid is None:
        if existing is not None:
            await session.delete(existing)
            await session.commit()
        return {"weekday": weekday, "program_id": None}
    user = await session.get(User, user_id)
    program = await load_program(session, int(str(pid)), user) if user else None
    if program is None:
        return {"error": "unknown program_id"}
    if existing is None:
        session.add(WeekdayProgram(user_id=user_id, weekday=weekday, program_id=program.id))
    else:
        existing.program_id = program.id
    await session.commit()
    return {"weekday": weekday, "program_id": program.id}


@tool(
    "import_training_days",
    "Create programs from the user's current PT plan's training days and pre-assign them to "
    "the same weekdays. Skips programs whose name already exists. Returns counts.",
    _EMPTY,
    writes=True,
)
async def _import_training_days(session: AsyncSession, args: JSON, user_id: int) -> object:
    user = await session.get(User, user_id)
    if user is None:
        return {"error": "unknown user"}
    return await import_training_days(session, user)


TOOLS: list[Tool] = _TOOLS
TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in _TOOLS}


def anthropic_tools(*, include_writes: bool = True) -> list[JSON]:
    """Tool definitions in the Anthropic Messages API shape.

    With include_writes=False the mutating tools are omitted entirely — used for
    read-only (trainer) chats so the model is never even offered a write.
    """
    return [
        {"name": t.name, "description": t.description, "input_schema": t.input_schema}
        for t in TOOLS
        if include_writes or not t.writes
    ]
