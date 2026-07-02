"""Execute features/shopping_list.feature via pytest-bdd (sync TestClient harness).

The weekly shopping list is generated from the active plan's meal ingredients, aggregated
by (name, unit) with each daily quantity multiplied by 7 for the week
(see app/services/shopping.py, WEEK_MULTIPLIER = 7).
"""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import delete, select

from app.models import Meal, MealIngredient, Plan
from tests.bdd.seed import full_plan

scenarios("shopping_list.feature")

_S = "/api/v1/shopping"
_START = date(2026, 5, 21)


# --- local seeders -----------------------------------------------------------


async def _reset_plans(session) -> None:
    """Drop any existing plan and its meals/ingredients.

    SQLite (test DB) doesn't enforce the ON DELETE CASCADE FKs and reuses rowids, so a
    bulk ``delete(Plan)`` would leave orphaned meals that a re-created plan (same id)
    then picks up. Delete the children explicitly.
    """
    await session.execute(delete(MealIngredient))
    await session.execute(delete(Meal))
    await session.execute(delete(Plan))


async def _chicken_plan(session) -> Plan:
    """A fresh current plan whose two meals both use 'cooked chicken' (100 g + 150 g)."""
    await _reset_plans(session)
    plan = Plan(is_current=True, start_date=_START, phase=1)
    session.add(plan)
    await session.flush()
    for num, slot, qty in ((1, "lunch", 100.0), (2, "dinner", 150.0)):
        meal = Meal(plan_id=plan.id, meal_number=num, slot=slot, name=f"Meal {num}")
        session.add(meal)
        await session.flush()
        session.add(
            MealIngredient(meal_id=meal.id, name="cooked chicken", quantity=qty, unit="g", order=0)
        )
    return plan


async def _add_ingredient(session, name: str, qty: float, unit: str) -> None:
    """Add an ingredient to the current plan's first meal."""
    plan = await session.scalar(select(Plan).where(Plan.is_current.is_(True)).limit(1))
    assert plan is not None
    meal = await session.scalar(select(Meal).where(Meal.plan_id == plan.id).limit(1))
    assert meal is not None
    session.add(MealIngredient(meal_id=meal.id, name=name, quantity=qty, unit=unit, order=99))


async def _new_meals_plan(session) -> Plan:
    """A fresh current plan with different ingredients than full_plan."""
    await _reset_plans(session)
    plan = Plan(is_current=True, start_date=_START, phase=2)
    session.add(plan)
    await session.flush()
    meal = Meal(plan_id=plan.id, meal_number=1, slot="breakfast", name="New breakfast")
    session.add(meal)
    await session.flush()
    session.add_all(
        [
            MealIngredient(
                meal_id=meal.id, name="Greek yoghurt", quantity=200.0, unit="g", order=0
            ),
            MealIngredient(meal_id=meal.id, name="Blueberries", quantity=50.0, unit="g", order=1),
        ]
    )
    return plan


# --- helpers -----------------------------------------------------------------


def _regenerate(client: TestClient) -> dict:
    resp = client.post(f"{_S}/regenerate")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _get(client: TestClient) -> dict:
    resp = client.get(_S)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _find(items: list[dict], name: str) -> list[dict]:
    return [i for i in items if i["name"] == name]


# --- Background --------------------------------------------------------------


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given("an active plan with meals and ingredients is in place")
def _active_plan(seed) -> None:
    seed(full_plan)


# --- Scenario: generated from the plan's meals -------------------------------


@when("I open the weekly shopping list")
def _open_list(bdd_client: TestClient, context: dict) -> None:
    _regenerate(bdd_client)  # build from the active plan's meals
    context["list"] = _get(bdd_client)


@then("it lists the ingredients needed for the week")
def _lists_ingredients(context: dict) -> None:
    items = context["list"]["items"]
    names = {i["name"] for i in items}
    assert "Oats" in names
    assert "Whey protein" in names


@then("quantities are aggregated across meals for 7 days")
def _aggregated_seven_days(context: dict) -> None:
    items = context["list"]["items"]
    oats = _find(items, "Oats")
    assert len(oats) == 1
    # full_plan: Oats 80 g in meal 1 only -> 80 * 7 for the week.
    assert oats[0]["quantity"] == 80 * 7
    assert oats[0]["unit"] == "g"


# --- Scenario: aggregate the same ingredient across meals --------------------


@given("two meals each use cooked chicken")
def _two_meals_chicken(seed) -> None:
    seed(_chicken_plan)


@then("the chicken appears once with the combined weekly quantity")
def _chicken_combined(context: dict) -> None:
    items = context["list"]["items"]
    chicken = _find(items, "cooked chicken")
    assert len(chicken) == 1, f"expected one chicken row, got {chicken}"
    # (100 + 150) g/day * 7 days = 1750 g for the week.
    assert chicken[0]["quantity"] == (100 + 150) * 7
    assert chicken[0]["unit"] == "g"


# --- Scenario: tick off items ------------------------------------------------


@when(parsers.parse('I check off "{name}"'))
def _check_off(bdd_client: TestClient, seed, context: dict, name: str) -> None:
    # Ensure the item exists on the list, then regenerate and tick it.
    seed(lambda s: _add_ingredient(s, name, 40.0, "g"))
    _regenerate(bdd_client)
    items = _get(bdd_client)["items"]
    target = _find(items, name)
    assert len(target) == 1, f"expected '{name}' on the list, got {[i['name'] for i in items]}"
    item_id = target[0]["id"]
    resp = bdd_client.patch(f"{_S}/items/{item_id}", json={"checked": True})
    assert resp.status_code == 200, resp.text
    context["item_id"] = item_id
    context["item_name"] = name


@then(parsers.parse('"{name}" is marked as bought'))
def _marked_bought(bdd_client: TestClient, context: dict, name: str) -> None:
    items = _get(bdd_client)["items"]
    target = _find(items, name)
    assert len(target) == 1
    assert target[0]["checked"] is True


@then("the checked state persists when I leave and return")
def _checked_persists(bdd_client: TestClient, context: dict) -> None:
    items = _get(bdd_client)["items"]  # fresh GET == leave and return
    target = _find(items, context["item_name"])
    assert len(target) == 1
    assert target[0]["checked"] is True


# --- Scenario: a new plan regenerates the shopping list ----------------------


@given("I approve a new plan with different meals")
def _approve_new_plan(seed) -> None:
    seed(_new_meals_plan)


@then("it reflects the new plan's ingredients")
def _reflects_new_plan(context: dict) -> None:
    items = context["list"]["items"]
    names = {i["name"] for i in items}
    assert "Greek yoghurt" in names
    assert "Blueberries" in names
    # The old plan's ingredients are gone.
    assert "Oats" not in names
    assert "Whey protein" not in names


# --- Scenario: reset the list for a new shopping trip ------------------------


@given("I have checked off several items")
def _checked_several(bdd_client: TestClient, context: dict) -> None:
    _regenerate(bdd_client)
    items = _get(bdd_client)["items"]
    assert items, "expected a non-empty list to check off"
    for item in items:
        resp = bdd_client.patch(f"{_S}/items/{item['id']}", json={"checked": True})
        assert resp.status_code == 200, resp.text
    # Confirm they are actually checked before the reset.
    assert all(i["checked"] for i in _get(bdd_client)["items"])


@when("I start a new shopping list for the week")
def _start_new_list(bdd_client: TestClient, context: dict) -> None:
    context["list"] = _regenerate(bdd_client)


@then("all items are unchecked again")
def _all_unchecked(bdd_client: TestClient, context: dict) -> None:
    items = _get(bdd_client)["items"]
    assert items, "expected items after regenerate"
    assert all(i["checked"] is False for i in items)
