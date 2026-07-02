"""Execute features/plan_detail.feature via pytest-bdd."""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy import delete

from app.models import Plan
from tests.bdd.seed import full_plan

scenarios("plan_detail.feature")

_D = "/api/v1/plans/current/detail"


@given("I am logged in")
def _login() -> None:
    pass


@given(parsers.parse("an active plan is in place, started on {d}"))
def _plan(seed, d: str) -> None:
    seed(lambda s: full_plan(s, start=date.fromisoformat(d)))


@given("there is no active plan")
def _no_plan(seed) -> None:
    async def _del(s):
        await s.execute(delete(Plan))

    seed(_del)


@given(parsers.parse('a meal "{name}" with ingredients'))
def _meal_with_ingredients(name: str) -> None:
    pass  # full_plan already seeds meal 1 with ingredients


@when("I open the current plan")
@when("I open that meal from the plan")
def _open(bdd_client: TestClient, context: dict) -> None:
    context["resp"] = bdd_client.get(_D)


def _detail(context: dict) -> dict:
    return context["resp"].json()


@then("I see the plan's start date")
def _start(context: dict) -> None:
    assert context["resp"].status_code == 200
    assert _detail(context)["start_date"] == "2026-05-21"


@then("how many days I've been on it")
def _days(context: dict) -> None:
    assert isinstance(_detail(context)["days_since_start"], int)


@then("I see each weekday mapped to its training day (or rest) and whether mobility is scheduled")
def _schedule(context: dict) -> None:
    sched = _detail(context)["schedule"]
    assert sched["monday"][0] == "Training Day 1"
    assert sched["monday"][1] is True


@then("I see each training day with its exercises, sets × reps and prescribed weights")
def _training_days(context: dict) -> None:
    tds = _detail(context)["training_days"]
    td1 = next(t for t in tds if t["label"] == "Training Day 1")
    lp = next(e for e in td1["exercises"] if e["slug"] == "leg-press-machine")
    assert lp["sets_x_reps"] == "4 × 15"
    assert lp["prescribed_weight"] == "50"


@then("I see each meal with its calories and macros")
def _meals(context: dict) -> None:
    m1 = next(m for m in _detail(context)["meals"] if m["meal_number"] == 1)
    assert m1["carbs_g"] == 74
    assert m1["calories"] == 500


@then(parsers.parse('I see each ingredient with its quantity and unit (e.g. "{example}")'))
def _ingredients(context: dict, example: str) -> None:
    m1 = next(m for m in _detail(context)["meals"] if m["meal_number"] == 1)
    assert m1["ingredients"]
    assert m1["ingredients"][0]["quantity"] is not None
    assert m1["ingredients"][0]["unit"] == "g"


@then("I see the steps, water, electrolyte and macro targets")
def _targets(context: dict) -> None:
    t = _detail(context)["targets"]
    assert t["steps_target"] == 7000
    assert t["daily_carbs_g"] == 212
    assert t["water_min_l"] == 2.0


@then("I am told there is no plan yet")
def _no_plan_msg(context: dict) -> None:
    assert context["resp"].status_code == 404
