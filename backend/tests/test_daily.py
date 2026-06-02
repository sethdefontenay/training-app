"""daily_task_list.feature: plan-driven day view, wellbeing, meal adherence, steps."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Exercise,
    Meal,
    Plan,
    Prescription,
    Session,
    SetEntry,
    StepsDay,
    TrainingDay,
    WeekdaySchedule,
)

TRAIN = date(2026, 5, 25)
REST = date(2026, 5, 26)  # different weekday with no schedule entry


async def _seed_plan(session: AsyncSession) -> Meal:
    plan = Plan(
        start_date=date(2026, 5, 21),
        is_current=True,
        steps_target=7000,
        water_min_l=2,
        water_max_l=3,
        electrolytes_per_day=1,
        daily_carbs_g=212,
    )
    session.add(plan)
    await session.flush()
    ex = Exercise(slug="leg-press-machine", name="Leg Press Machine")
    session.add(ex)
    await session.flush()
    td = TrainingDay(plan_id=plan.id, label="Training Day 1", order=0)
    session.add(td)
    await session.flush()
    session.add(
        Prescription(
            training_day_id=td.id,
            exercise_id=ex.id,
            sets_x_reps="4 × 15",
            prescribed_weight="10",
            order=0,
        )
    )
    session.add(
        WeekdaySchedule(
            plan_id=plan.id,
            weekday=TRAIN.strftime("%A").lower(),
            training_day_id=td.id,
            has_mobility=True,
        )
    )
    meal = Meal(
        plan_id=plan.id,
        meal_number=1,
        slot="breakfast",
        name="Protein oats",
        calories=620,
        protein_g=42,
        carbs_g=74,
        fat_g=11,
    )
    session.add(meal)
    await session.flush()
    await session.commit()
    return meal


async def test_today_reflects_plan(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed_plan(session)
    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    assert view["has_plan"] is True
    assert view["workout"]["label"] == "Training Day 1"
    line = view["workout"]["exercises"][0]
    assert line["slug"] == "leg-press-machine"
    assert line["target_sets"] == 4
    assert view["meals"][0]["carbs_g"] == 74
    assert view["daily_carbs_total"] == 212
    assert view["targets"]["steps_target"] == 7000


async def test_rest_day_has_no_workout_but_meals(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_plan(session)
    view = (await auth_client.get(f"/api/v1/daily/{REST.isoformat()}")).json()
    assert view["workout"] is None
    assert len(view["meals"]) == 1


async def test_meal_check_records_adherence(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    meal = await _seed_plan(session)
    r = await auth_client.post(f"/api/v1/daily/{TRAIN.isoformat()}/meals/{meal.id}/check")
    assert r.status_code == 200
    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    eaten = next(m for m in view["meals"] if m["id"] == meal.id)
    assert eaten["eaten"] is True
    assert eaten["carbs_g"] == 74  # carb figure unchanged by checking


async def test_wellbeing_upsert_and_edit(auth_client: AsyncClient) -> None:
    await auth_client.put(
        f"/api/v1/daily/{TRAIN.isoformat()}/wellbeing",
        json={"energy": 7, "motivation": 6, "stress": 4, "hunger": 5},
    )
    again = await auth_client.put(
        f"/api/v1/daily/{TRAIN.isoformat()}/wellbeing", json={"energy": 5}
    )
    assert again.json()["energy"] == 5
    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    assert view["wellbeing"]["energy"] == 5
    assert view["wellbeing"]["motivation"] == 6  # preserved


async def test_wellbeing_out_of_range_rejected(auth_client: AsyncClient) -> None:
    r = await auth_client.put(f"/api/v1/daily/{TRAIN.isoformat()}/wellbeing", json={"energy": 11})
    assert r.status_code == 422


async def test_workout_progress_from_logged_sets(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_plan(session)
    ex = await session.scalar(select(Exercise).where(Exercise.slug == "leg-press-machine"))
    s = Session(date=TRAIN, weekday=TRAIN.strftime("%A"))
    session.add(s)
    await session.flush()
    for i in (1, 2):
        session.add(
            SetEntry(session_id=s.id, exercise_id=ex.id, set_index=i, reps="15", weight="40")
        )
    await session.commit()

    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    assert view["workout"]["exercises"][0]["completed_sets"] == 2


async def test_steps_progress_from_sync(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed_plan(session)
    session.add(StepsDay(date=TRAIN, steps=4200, target_steps=7000))
    await session.commit()
    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    assert view["steps"]["steps"] == 4200
    assert view["steps"]["target"] == 7000
