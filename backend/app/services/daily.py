"""Resolve the daily task list: today's plan content + logged state."""

import re
from collections.abc import Sequence
from datetime import date
from typing import Any

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
from app.services.programs import program_for_weekday
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

    return await _build_block(
        session, td.label, sorted(td.prescriptions, key=lambda x: x.order), day, user_id
    )


async def _build_block(
    session: AsyncSession, label: str, rows: Sequence[Any], day: date, user_id: int
) -> WorkoutBlock:
    """Build a WorkoutBlock from prescription-like rows (Prescription or ProgramExercise;
    each exposes .exercise_id, .exercise (slug/name), .sets_x_reps, .prescribed_weight).
    Completed-set counts and the last-week column come from the user's own sessions, so
    they work identically whether the day is planner- or PT-plan-driven."""
    exercise_ids = [r.exercise_id for r in rows]

    # Completed-set counts for today, all exercises in one grouped query (was N queries).
    sess = await session.scalar(
        select(Session).where(Session.date == day, Session.user_id == user_id)
    )
    completed_by_ex: dict[int, int] = {}
    if sess is not None:
        counted = (
            await session.execute(
                select(SetEntry.exercise_id, func.count())
                .where(SetEntry.session_id == sess.id)
                .group_by(SetEntry.exercise_id)
            )
        ).all()
        completed_by_ex = {row[0]: row[1] for row in counted}

    last_weeks = await last_week_for_exercises(session, exercise_ids, day, user_id)

    lines = [
        ExerciseLine(
            slug=r.exercise.slug,
            name=r.exercise.name,
            sets_x_reps=r.sets_x_reps,
            prescribed_weight=r.prescribed_weight,
            target_sets=_target_sets(r.sets_x_reps),
            completed_sets=completed_by_ex.get(r.exercise_id, 0),
            last_week=last_weeks.get(r.exercise_id, NO_HISTORY),
        )
        for r in rows
    ]
    return WorkoutBlock(label=label, exercises=lines)


async def _workout_block_from_program(
    session: AsyncSession, program: Any, day: date, user_id: int
) -> WorkoutBlock:
    """Build the day's block from a user-owned program (planner path)."""
    return await _build_block(
        session, program.name, sorted(program.exercises, key=lambda e: e.order), day, user_id
    )


async def resolve_day(session: AsyncSession, day: date, user_id: int) -> DailyView:
    weekday = day.strftime("%A").lower()
    plan = await _current_plan(session, user_id)

    workout: WorkoutBlock | None = None
    mobility: list[MobilityItem] | None = None
    meals: list[MealLine] = []
    daily_carbs_total: int | None = None
    targets: dict[str, float | int | None] = {}

    # Workout source: the user's planner assignment for this weekday takes precedence;
    # the PT plan's WeekdaySchedule is the fallback when no program is assigned. This is
    # independent of the PT plan existing, so the planner drives the day on its own.
    program = await program_for_weekday(session, user_id, weekday)
    if program is not None:
        workout = await _workout_block_from_program(session, program, day, user_id)
    elif plan is not None:
        workout = await _workout_block(session, plan, weekday, day, user_id)
    # Show a mobility section on workout days.
    if workout is not None:
        mobility = await _mobility_for(session, day, user_id)

    if plan is not None:
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
