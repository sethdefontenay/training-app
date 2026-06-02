"""Generate the weekly shopping list from the active plan's meal ingredients."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meal, MealIngredient, Plan, ShoppingItem, ShoppingList

WEEK_MULTIPLIER = 7  # vault behaviour: daily meal ingredients × 7 for the week


async def current_plan(session: AsyncSession) -> Plan | None:
    plan: Plan | None = await session.scalar(select(Plan).where(Plan.is_current.is_(True)).limit(1))
    return plan


async def generate_for_plan(session: AsyncSession, plan: Plan, week_start: date) -> ShoppingList:
    ingredients = (
        (
            await session.execute(
                select(MealIngredient)
                .join(Meal, MealIngredient.meal_id == Meal.id)
                .where(Meal.plan_id == plan.id)
            )
        )
        .scalars()
        .all()
    )
    # Aggregate by (name, unit), multiplying daily quantities for the week.
    agg: dict[tuple[str, str | None], float | None] = {}
    for ing in ingredients:
        key = (ing.name, ing.unit)
        if ing.quantity is None:
            agg.setdefault(key, None)
        else:
            agg[key] = (agg.get(key) or 0.0) + ing.quantity * WEEK_MULTIPLIER

    sl = ShoppingList(plan_id=plan.id, week_start=week_start)
    session.add(sl)
    await session.flush()
    for (name, unit), qty in sorted(agg.items()):
        session.add(ShoppingItem(shopping_list_id=sl.id, name=name, unit=unit, quantity=qty))
    await session.commit()
    await session.refresh(sl)
    return sl
