"""Commit a reviewed plan proposal: new current plan, archive the old one, keep history."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Meal,
    MealIngredient,
    Plan,
    Prescription,
    TrainingDay,
    WeekdaySchedule,
)
from app.schemas.plan_ingest import ProposedPlan
from app.services.shopping import generate_for_plan
from app.services.workouts import get_or_create_exercise


async def commit_plan(session: AsyncSession, proposed: ProposedPlan, start_date: date) -> Plan:
    # Archive whatever is current — kept, just no longer active.
    current = await session.scalar(select(Plan).where(Plan.is_current.is_(True)))
    if current is not None:
        current.is_current = False

    plan = Plan(
        start_date=start_date,
        is_current=True,
        source=proposed.source,
        phase=proposed.phase,
        guidance=proposed.guidance,
        steps_target=proposed.steps_target,
        water_min_l=proposed.water_min_l,
        water_max_l=proposed.water_max_l,
        electrolytes_per_day=proposed.electrolytes_per_day,
        daily_calories=proposed.daily_calories,
        daily_protein_g=proposed.daily_protein_g,
        daily_carbs_g=proposed.daily_carbs_g,
        daily_fat_g=proposed.daily_fat_g,
    )
    session.add(plan)
    await session.flush()

    for td in proposed.training_days:
        day = TrainingDay(plan_id=plan.id, label=td.label, order=td.order)
        session.add(day)
        await session.flush()
        if td.weekday:
            session.add(
                WeekdaySchedule(
                    plan_id=plan.id,
                    weekday=td.weekday.lower(),
                    training_day_id=day.id,
                    has_mobility=True,
                )
            )
        for pr in td.prescriptions:
            ex = await get_or_create_exercise(session, pr.exercise_slug)
            ex.name = pr.exercise_name
            ex.is_bodyweight = pr.is_bodyweight
            session.add(
                Prescription(
                    training_day_id=day.id,
                    exercise_id=ex.id,
                    sets_x_reps=pr.sets_x_reps,
                    prescribed_weight=pr.prescribed_weight,
                    order=pr.order,
                )
            )

    for m in proposed.meals:
        meal = Meal(
            plan_id=plan.id,
            meal_number=m.meal_number,
            slot=m.slot,
            name=m.name,
            calories=m.calories,
            protein_g=m.protein_g,
            carbs_g=m.carbs_g,
            fat_g=m.fat_g,
        )
        session.add(meal)
        await session.flush()
        for ing in m.ingredients:
            session.add(
                MealIngredient(meal_id=meal.id, name=ing.name, quantity=ing.quantity, unit=ing.unit)
            )

    await session.commit()
    # Derived output: a fresh weekly shopping list from the new plan's meals.
    await generate_for_plan(session, plan, start_date)
    return plan
