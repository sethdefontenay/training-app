"""Resolve the daily task list: today's plan content + logged state."""

import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DailyLog,
    DailyWellbeing,
    Exercise,
    Meal,
    MealCheck,
    MobilityDone,
    Plan,
    Prescription,
    Session,
    SetEntry,
    StepsDay,
    TrainingDay,
    WeekdaySchedule,
)
from app.schemas.daily import (
    DailyView,
    ExerciseLine,
    MealLine,
    MobilityItem,
    WellbeingIn,
    WorkoutBlock,
)
from app.services.workouts import NO_HISTORY, last_week_for_exercises


async def _mobility_for(session: AsyncSession, day: date, user_id: int) -> list[MobilityItem]:
    """The mobility checklist = the moves you actually do (from history), with today's
    done-state. (Derived from MobilityDone; upgrade to a prescribed round when available.)"""
    catalog = (
        await session.execute(
            select(Exercise.slug, Exercise.name)
            .join(MobilityDone, MobilityDone.exercise_id == Exercise.id)
            .where(MobilityDone.user_id == user_id)
            .distinct()
            .order_by(Exercise.name)
        )
    ).all()
    done_today = set(
        (
            await session.execute(
                select(Exercise.slug)
                .join(MobilityDone, MobilityDone.exercise_id == Exercise.id)
                .where(MobilityDone.date == day, MobilityDone.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    return [MobilityItem(slug=s, name=n, done=s in done_today) for s, n in catalog]


def _target_sets(sets_x_reps: str) -> int | None:
    m = re.match(r"\s*(\d+)", sets_x_reps)
    return int(m.group(1)) if m else None


async def _current_plan(session: AsyncSession, user_id: int) -> Plan | None:
    plan: Plan | None = await session.scalar(
        select(Plan).where(Plan.is_current.is_(True), Plan.user_id == user_id).limit(1)
    )
    return plan


async def _workout_block(
    session: AsyncSession, plan: Plan, weekday: str, day: date, user_id: int
) -> WorkoutBlock | None:
    sched = await session.scalar(
        select(WeekdaySchedule).where(
            WeekdaySchedule.plan_id == plan.id, WeekdaySchedule.weekday == weekday
        )
    )
    if sched is None or sched.training_day_id is None:
        return None
    td = await session.scalar(
        select(TrainingDay)
        .where(TrainingDay.id == sched.training_day_id)
        .options(selectinload(TrainingDay.prescriptions).selectinload(Prescription.exercise))
    )
    if td is None:
        return None

    prescriptions = sorted(td.prescriptions, key=lambda x: x.order)
    exercise_ids = [p.exercise_id for p in prescriptions]

    # Completed-set counts for today, all exercises in one grouped query (was N queries).
    sess = await session.scalar(
        select(Session).where(Session.date == day, Session.user_id == user_id)
    )
    completed_by_ex: dict[int, int] = {}
    if sess is not None:
        rows = (
            await session.execute(
                select(SetEntry.exercise_id, func.count())
                .where(SetEntry.session_id == sess.id)
                .group_by(SetEntry.exercise_id)
            )
        ).all()
        completed_by_ex = {row[0]: row[1] for row in rows}

    # Last-week numbers for every exercise in one query, computed server-side so the
    # frontend no longer fires a request per exercise (the old N+1 + slow-load bug).
    last_weeks = await last_week_for_exercises(session, exercise_ids, day, user_id)

    lines = [
        ExerciseLine(
            slug=p.exercise.slug,
            name=p.exercise.name,
            sets_x_reps=p.sets_x_reps,
            prescribed_weight=p.prescribed_weight,
            target_sets=_target_sets(p.sets_x_reps),
            completed_sets=completed_by_ex.get(p.exercise_id, 0),
            last_week=last_weeks.get(p.exercise_id, NO_HISTORY),
        )
        for p in prescriptions
    ]
    return WorkoutBlock(label=td.label, exercises=lines)


async def resolve_day(session: AsyncSession, day: date, user_id: int) -> DailyView:
    weekday = day.strftime("%A").lower()
    plan = await _current_plan(session, user_id)

    workout: WorkoutBlock | None = None
    mobility: list[MobilityItem] | None = None
    meals: list[MealLine] = []
    daily_carbs_total: int | None = None
    targets: dict[str, float | int | None] = {}

    if plan is not None:
        workout = await _workout_block(session, plan, weekday, day, user_id)
        # Show a mobility section on workout days.
        if workout is not None:
            mobility = await _mobility_for(session, day, user_id)
        plan_meals = (
            (
                await session.execute(
                    select(Meal).where(Meal.plan_id == plan.id).order_by(Meal.meal_number)
                )
            )
            .scalars()
            .all()
        )
        eaten_ids = set(
            (
                await session.execute(
                    select(MealCheck.meal_id).where(
                        MealCheck.date == day,
                        MealCheck.eaten.is_(True),
                        MealCheck.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for m in plan_meals:
            meals.append(
                MealLine(
                    id=m.id,
                    meal_number=m.meal_number,
                    slot=m.slot,
                    name=m.name,
                    carbs_g=m.carbs_g,
                    calories=m.calories,
                    protein_g=m.protein_g,
                    fat_g=m.fat_g,
                    eaten=m.id in eaten_ids,
                )
            )
        daily_carbs_total = plan.daily_carbs_g or sum((m.carbs_g or 0) for m in plan_meals)
        targets = {
            "steps_target": plan.steps_target,
            "water_min_l": plan.water_min_l,
            "water_max_l": plan.water_max_l,
            "electrolytes_per_day": plan.electrolytes_per_day,
        }

    steps_row = await session.scalar(
        select(StepsDay).where(StepsDay.date == day, StepsDay.user_id == user_id)
    )
    wb = await session.scalar(
        select(DailyWellbeing).where(DailyWellbeing.date == day, DailyWellbeing.user_id == user_id)
    )
    log = await session.scalar(
        select(DailyLog).where(DailyLog.date == day, DailyLog.user_id == user_id)
    )

    return DailyView(
        date=day,
        weekday=day.strftime("%A"),
        has_plan=plan is not None,
        workout=workout,
        mobility=mobility,
        meals=meals,
        daily_carbs_total=daily_carbs_total,
        targets=targets,
        steps={
            "steps": steps_row.steps if steps_row else None,
            "target": (steps_row.target_steps if steps_row else None)
            or (plan.steps_target if plan else None),
        },
        wellbeing=WellbeingIn(
            energy=wb.energy if wb else None,
            motivation=wb.motivation if wb else None,
            stress=wb.stress if wb else None,
            hunger=wb.hunger if wb else None,
        ),
        water_units=log.water_units if log else 0,
        electrolytes_done=log.electrolytes_done if log else False,
        notes=log.notes if log else None,
    )
