"""shopping_list.feature: generation from plan meals, aggregation, checking, regenerate."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meal, MealIngredient, Plan, User


async def _seed(session: AsyncSession) -> None:
    uid = int(await session.scalar(select(User.id).order_by(User.id).limit(1)))
    plan = Plan(user_id=uid, start_date=date(2026, 5, 21), is_current=True)
    session.add(plan)
    await session.flush()
    m1 = Meal(plan_id=plan.id, meal_number=1, slot="lunch", name="Chicken rice")
    m2 = Meal(plan_id=plan.id, meal_number=2, slot="dinner", name="Chicken bowl")
    session.add_all([m1, m2])
    await session.flush()
    session.add_all(
        [
            MealIngredient(meal_id=m1.id, name="cooked chicken", quantity=150, unit="g"),
            MealIngredient(meal_id=m2.id, name="cooked chicken", quantity=180, unit="g"),
            MealIngredient(meal_id=m1.id, name="rice", quantity=80, unit="g"),
        ]
    )
    await session.commit()


async def test_generated_and_aggregated(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session)
    data = (await auth_client.get("/api/v1/shopping")).json()
    chicken = next(i for i in data["items"] if i["name"] == "cooked chicken")
    assert chicken["quantity"] == (150 + 180) * 7  # aggregated across meals, ×7


async def test_check_item_persists(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session)
    data = (await auth_client.get("/api/v1/shopping")).json()
    item_id = data["items"][0]["id"]
    await auth_client.patch(f"/api/v1/shopping/items/{item_id}", json={"checked": True})
    again = (await auth_client.get("/api/v1/shopping")).json()
    checked = next(i for i in again["items"] if i["id"] == item_id)
    assert checked["checked"] is True


async def test_regenerate_unchecks(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session)
    data = (await auth_client.get("/api/v1/shopping")).json()
    await auth_client.patch(
        f"/api/v1/shopping/items/{data['items'][0]['id']}", json={"checked": True}
    )
    fresh = (await auth_client.post("/api/v1/shopping/regenerate")).json()
    assert all(i["checked"] is False for i in fresh["items"])
