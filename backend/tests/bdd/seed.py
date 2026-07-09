"""Async seeding building blocks for the pytest-bdd suite.

Each function takes an AsyncSession and writes rows; the `seed` fixture commits. Used for
data with no write endpoint (the synced/integration tables) and the canonical active plan.
Sessions, sets, mobility ticks and meal checks are seeded via the API in the step files.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exercise,
    GlucoseReading,
    InsulinEvent,
    IntegrationSetting,
    Meal,
    MealIngredient,
    Plan,
    Prescription,
    SleepNight,
    StepsDay,
    TrainingDay,
    User,
    WeekdaySchedule,
)


async def _owner_id(session: AsyncSession) -> int:
    """The BDD owner's id (seeded first in bdd_env, so it has the lowest id)."""
    return int(await session.scalar(select(User.id).order_by(User.id).limit(1)))


# Canonical exercise catalog (slug -> (name, is_bodyweight)).
_EXERCISES = {
    "leg-press-machine": ("Leg Press Machine", False),
    "lat-pulldown": ("Lat Pulldown", False),
    "seated-pulley-row": ("Seated Pulley Row", False),
    "crunches": ("Crunches", True),
    "flat-chest-press": ("Flat Chest Press", False),
    "pec-deck-machine": ("Pec Deck Machine", False),
    "leg-extension": ("Leg Extension", False),
    "shoulder-press": ("Shoulder Press", False),
    "smith-machine-squat": ("Smith Machine Squat", False),
    "rear-delt-fly-machine": ("Rear Delt Fly Machine", False),
    "bird-dog": ("Bird Dog", True),
    "cat-cow": ("Cat-Cow", True),
    "shoulder-cars": ("Shoulder CARs", True),
}

# (slug, sets_x_reps, prescribed_weight) per training day.
_TRAINING_DAYS = {
    "Training Day 1": [
        ("leg-press-machine", "4 × 15", "50"),
        ("lat-pulldown", "3 × 15", "47"),
        ("seated-pulley-row", "3 × 15", "57"),
        ("crunches", "4 × 15", None),
    ],
    "Training Day 2": [
        ("flat-chest-press", "3 × 12", "40"),
        ("pec-deck-machine", "3 × 15", "35"),
        ("leg-extension", "3 × 15", "45"),
    ],
    "Training Day 3": [
        ("shoulder-press", "4 × 15", "25"),
        ("smith-machine-squat", "3 × 15", "20"),
        ("rear-delt-fly-machine", "3 × 12", "85"),
    ],
}

# meal_number, slot, name, calories, protein, carbs, fat  (carbs sum to 212 = daily target)
_MEALS = [
    (1, "breakfast", "Meal 1 — Breakfast", 500, 40, 74, 15),
    (2, "lunch", "Meal 2 — Lunch", 650, 50, 46, 20),
    (3, "snack", "Meal 3 — Snack", 400, 33, 46, 18),
    (4, "dinner", "Meal 4 — Dinner", 700, 50, 46, 30),
]


async def _exercises(session: AsyncSession) -> dict[str, Exercise]:
    out: dict[str, Exercise] = {}
    for slug, (name, bw) in _EXERCISES.items():
        ex = Exercise(slug=slug, name=name, is_bodyweight=bw)
        session.add(ex)
        out[slug] = ex
    await session.flush()
    return out


async def full_plan(session: AsyncSession, start: date = date(2026, 5, 21)) -> Plan:
    """The canonical active plan the plan-dependent features assert against.

    Mon→Training Day 1, Wed→Training Day 2, Fri→Training Day 3 (all with mobility);
    other days rest. Four meals (carbs 74/46/46/46 = 212). Targets: 7000 steps, 2–3 L
    water, 1 electrolyte, 2400 kcal / 173P / 212C / 83F.
    """
    ex = await _exercises(session)
    plan = Plan(
        user_id=await _owner_id(session),
        is_current=True,
        start_date=start,
        phase=1,
        source="PT, 2026-05-21",
        guidance="Train around the shoulders; non-negotiables: sleep and hydration.",
        steps_target=7000,
        water_min_l=2.0,
        water_max_l=3.0,
        electrolytes_per_day=1,
        daily_calories=2400,
        daily_protein_g=173,
        daily_carbs_g=212,
        daily_fat_g=83,
    )
    session.add(plan)
    await session.flush()

    days: dict[str, TrainingDay] = {}
    for order, (label, presc) in enumerate(_TRAINING_DAYS.items()):
        td = TrainingDay(plan_id=plan.id, label=label, order=order)
        session.add(td)
        await session.flush()
        days[label] = td
        for i, (slug, sxr, wt) in enumerate(presc):
            session.add(
                Prescription(
                    training_day_id=td.id,
                    exercise_id=ex[slug].id,
                    sets_x_reps=sxr,
                    prescribed_weight=wt,
                    order=i,
                )
            )

    for weekday, label in (
        ("monday", "Training Day 1"),
        ("wednesday", "Training Day 2"),
        ("friday", "Training Day 3"),
    ):
        session.add(
            WeekdaySchedule(
                plan_id=plan.id, weekday=weekday, training_day_id=days[label].id, has_mobility=True
            )
        )

    for num, slot, name, cals, p, c, f in _MEALS:
        meal = Meal(
            plan_id=plan.id,
            meal_number=num,
            slot=slot,
            name=name,
            calories=cals,
            protein_g=p,
            carbs_g=c,
            fat_g=f,
        )
        session.add(meal)
        await session.flush()
        if num == 1:
            session.add_all(
                [
                    MealIngredient(meal_id=meal.id, name="Oats", quantity=80, unit="g", order=0),
                    MealIngredient(
                        meal_id=meal.id, name="Whey protein", quantity=30, unit="g", order=1
                    ),
                ]
            )
    return plan


async def add_steps(session: AsyncSession, day: date, steps: int, target: int = 7000) -> None:
    session.add(
        StepsDay(
            user_id=await _owner_id(session),
            date=day,
            steps=steps,
            target_steps=target,
            target_met=steps >= target,
        )
    )


async def add_sleep(session: AsyncSession, day: date, *, with_stages: bool = True) -> None:
    stages = (
        [
            {"type": "light", "start": f"{day}T22:30:00", "end": f"{day}T23:30:00"},
            {"type": "deep", "start": f"{day}T23:30:00", "end": f"{day}T01:30:00"},
            {"type": "rem", "start": f"{day}T05:00:00", "end": f"{day}T06:00:00"},
        ]
        if with_stages
        else None
    )
    session.add(
        SleepNight(
            user_id=await _owner_id(session),
            date=day,
            bedtime="22:30",
            wake_time="07:00",
            asleep_min=420.0,
            in_bed_min=450.0,
            awake_min=15.0,
            light_min=200.0,
            deep_min=150.0,
            rem_min=70.0,
            efficiency=93.0,
            stages=stages,
            sessions=1,
            device="fitbit",
        )
    )


def _nz(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo("Pacific/Auckland"))


async def add_glucose(session: AsyncSession, day: date, hour: int, mmol: float) -> None:
    session.add(GlucoseReading(user_id=await _owner_id(session), ts=_nz(day, hour), mmol_l=mmol))


async def add_insulin(
    session: AsyncSession, day: date, hour: int, units: float, carbs: float | None = None
) -> None:
    session.add(
        InsulinEvent(
            user_id=await _owner_id(session),
            ts=_nz(day, hour),
            kind="bolus",
            units=units,
            carbs_g=carbs,
        )
    )


async def set_integration(session: AsyncSession, key: str, value: str) -> None:
    session.add(IntegrationSetting(key=key, value=value))
