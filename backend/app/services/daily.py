"""Resolve the daily task list: today's plan content + logged state."""

import re
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    DailyLog,
    DailyWellbeing,
    Meal,
    MealCheck,
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
    WellbeingIn,
    WorkoutBlock,
)


def _target_sets(sets_x_reps: str) -> int | None:
    m = re.match(r"\s*(\d+)", sets_x_reps)
    return int(m.group(1)) if m else None


async def _current_plan(session: AsyncSession) -> Plan | None:
    plan: Plan | None = await session.scalar(select(Plan).where(Plan.is_current.is_(True)).limit(1))
    return plan


async def _workout_block(
    session: AsyncSession, plan: Plan, weekday: str, day: date
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

    sess = await session.scalar(select(Session).where(Session.date == day))
    lines: list[ExerciseLine] = []
    for p in sorted(td.prescriptions, key=lambda x: x.order):
        completed = 0
        if sess is not None:
            completed = (
                await session.scalar(
                    select(func.count())
                    .select_from(SetEntry)
                    .where(
                        SetEntry.session_id == sess.id,
                        SetEntry.exercise_id == p.exercise_id,
                    )
                )
            ) or 0
        lines.append(
            ExerciseLine(
                slug=p.exercise.slug,
                name=p.exercise.name,
                sets_x_reps=p.sets_x_reps,
                prescribed_weight=p.prescribed_weight,
                target_sets=_target_sets(p.sets_x_reps),
                completed_sets=completed,
            )
        )
    return WorkoutBlock(label=td.label, exercises=lines)


async def resolve_day(session: AsyncSession, day: date) -> DailyView:
    weekday = day.strftime("%A").lower()
    plan = await _current_plan(session)

    workout: WorkoutBlock | None = None
    meals: list[MealLine] = []
    daily_carbs_total: int | None = None
    targets: dict[str, float | int | None] = {}

    if plan is not None:
        workout = await _workout_block(session, plan, weekday, day)
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
                        MealCheck.date == day, MealCheck.eaten.is_(True)
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

    steps_row = await session.scalar(select(StepsDay).where(StepsDay.date == day))
    wb = await session.scalar(select(DailyWellbeing).where(DailyWellbeing.date == day))
    log = await session.scalar(select(DailyLog).where(DailyLog.date == day))

    return DailyView(
        date=day,
        weekday=day.strftime("%A"),
        has_plan=plan is not None,
        workout=workout,
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
