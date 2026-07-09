"""Full migration: importing the Obsidian Plan/ + Schedule/ into an active plan."""

import textwrap
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.importer import import_vault
from app.models import (
    Exercise,
    Meal,
    MealIngredient,
    Plan,
    Prescription,
    ShoppingItem,
    TrainingDay,
    User,
    WeekdaySchedule,
)


def _w(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def _build_plan_vault(root: Path) -> Path:
    v = root / "vault"
    _w(
        v / "Plan" / "Meal-Plan-1.md",
        """
        ---
        type: meal-plan
        current: true
        phase: 1
        source: "Holly, 2026-05-21"
        ---
        """,
    )
    _w(v / "Plan" / "Overview.md", "Aim for 7,000 steps/day. Water 2–3L. 1 electrolyte serve.\n")
    _w(
        v / "Plan" / "Training-Day-1.md",
        r"""
        ---
        weekday: Monday
        ---
        # Day 1

        | # | Exercise | Sets × Reps | Notes | Weight Lifted |
        |---|----------|-------------|-------|---------------|
        | 1 | [[leg-press-machine\|Leg Press Machine]] | 4 × 15 | | 40kg |
        | 2 | [[crunches\|Crunches]] | 4 × 15 | on back | |
        """,
    )
    _w(
        v / "Plan" / "Meals" / "Meal-1-Breakfast.md",
        """
        ---
        meal: 1
        slot: breakfast
        calories: 620
        protein: 42
        carbs: 74
        fat: 11
        ---
        # Protein oats

        ## Ingredients
        - 80g oats
        - 300ml trim milk
        """,
    )
    _w(
        v / "Schedule" / "Weekly-Schedule.md",
        """
        ---
        monday:
          - "[[Training-Day-1]]"
          - "[[Mobility]]"
        ---
        """,
    )
    return v


async def test_full_plan_import(tmp_path: Path, session: AsyncSession, user: User) -> None:
    vault = _build_plan_vault(tmp_path)
    await import_vault(session, vault, user.id)

    plan = await session.scalar(select(Plan).where(Plan.is_current.is_(True)))
    assert plan is not None
    assert plan.source == "Holly, 2026-05-21"
    assert plan.start_date.isoformat() == "2026-05-21"
    assert plan.steps_target == 7000
    assert plan.daily_carbs_g == 74

    td = await session.scalar(select(TrainingDay).where(TrainingDay.plan_id == plan.id))
    assert td is not None and td.label == "Training Day 1"

    legpress = await session.scalar(
        select(Prescription).join(Exercise).where(Exercise.slug == "leg-press-machine")
    )
    assert legpress is not None
    assert legpress.sets_x_reps == "4 × 15"
    assert legpress.prescribed_weight == "40"

    crunches = await session.scalar(select(Exercise).where(Exercise.slug == "crunches"))
    assert crunches is not None and crunches.is_bodyweight is True

    sched = await session.scalar(select(WeekdaySchedule).where(WeekdaySchedule.weekday == "monday"))
    assert sched is not None
    assert sched.training_day_id == td.id
    assert sched.has_mobility is True

    meal = await session.scalar(select(Meal).where(Meal.plan_id == plan.id))
    assert meal is not None and meal.carbs_g == 74
    oats = await session.scalar(select(MealIngredient).where(MealIngredient.name == "oats"))
    assert oats is not None and oats.quantity == 80 and oats.unit == "g"

    oats_item = await session.scalar(select(ShoppingItem).where(ShoppingItem.name == "oats"))
    assert oats_item is not None and oats_item.quantity == 80 * 7


async def test_plan_import_is_idempotent(tmp_path: Path, session: AsyncSession, user: User) -> None:
    vault = _build_plan_vault(tmp_path)
    await import_vault(session, vault, user.id)
    await import_vault(session, vault, user.id)
    assert (await session.scalar(select(func.count()).select_from(Plan))) == 1
