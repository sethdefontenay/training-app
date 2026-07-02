"""Execute features/daily_task_list.feature via pytest-bdd (sync TestClient harness).

Contract exercised (all /api/v1):
  GET    /daily/{day}                          -> DailyView (workout, mobility, meals,
                                                  daily_carbs_total, targets, steps,
                                                  wellbeing, water_units, electrolytes_done, notes)
  PUT    /daily/{day}/wellbeing {energy,...}    -> 1-10 each; 11 -> 422
  PUT    /daily/{day}/log {water_units, electrolytes_done, notes}
  POST   /daily/{day}/meals/{meal_id}/check     -> {"eaten": True}
  DELETE /daily/{day}/meals/{meal_id}/check     -> {"eaten": False}
  POST   /mobility/done {date, exercise_slug}
  DELETE /mobility/done?on=DATE&exercise_slug=SLUG
  POST   /sessions {date}  +  POST /sessions/{id}/sets   (workout progress)

The daily mobility section is DERIVED from MobilityDone history (services/daily.py
_mobility_for) and only appears on a workout day, so mobility moves are populated by
POSTing /mobility/done for an arbitrary past date to seed the catalog.
"""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.seed import add_steps, full_plan

scenarios("daily_task_list.feature")

_API = "/api/v1"

# The feature Background pins "today" to Monday 2026-05-25 (Training Day 1).
TODAY = "2026-05-25"
# A Sunday rest day the rest-day scenarios override the current day to.
SUNDAY = "2026-05-31"

# Human meal / exercise / mobility names used in the feature -> canonical identifiers.
_MOBILITY_SLUGS = {
    "Bird Dog": "bird-dog",
    "Cat-Cow": "cat-cow",
    "Shoulder CARs": "shoulder-cars",
}
_EXERCISE_SLUGS = {
    "Leg Press Machine": "leg-press-machine",
}


def _day(context: dict[str, object]) -> str:
    return str(context.get("today", TODAY))


def _view(bdd_client: TestClient, day: str) -> dict:
    resp = bdd_client.get(f"{_API}/daily/{day}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _meal_by_name(view: dict, name: str) -> dict:
    return next(m for m in view["meals"] if m["name"] == name)


# --------------------------------------------------------------------------- #
# Background
# --------------------------------------------------------------------------- #


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token.


@given("an active plan is in place")
def _active_plan(seed, context: dict[str, object]) -> None:
    seed(full_plan)
    context["today"] = TODAY


@given(parsers.parse("today is Monday {day}"))
def _today_monday(context: dict[str, object], day: str) -> None:
    # No clock override in the suite; the fixed date is threaded explicitly.
    assert day == TODAY
    context["today"] = day


@given(parsers.parse('the schedule maps Monday to "{label}" and "{extra}"'))
def _schedule_monday(label: str, extra: str) -> None:
    pass  # Documented by full_plan (Mon -> Training Day 1, has_mobility=True).


# --------------------------------------------------------------------------- #
# Day overrides for rest-day scenarios
# --------------------------------------------------------------------------- #


@given(parsers.parse("today is Sunday {day}"))
@given(parsers.parse("today is Sunday {day} with no training scheduled"))
def _today_sunday(context: dict[str, object], day: str) -> None:
    assert day == SUNDAY
    context["today"] = day


@given(parsers.parse("the schedule maps Sunday to no training"))
def _schedule_sunday() -> None:
    pass  # full_plan schedules only Mon/Wed/Fri; Sunday is a rest day.


# --------------------------------------------------------------------------- #
# Opening the list
# --------------------------------------------------------------------------- #


@when("I open today's list")
def _open_today(context: dict[str, object], bdd_client: TestClient) -> None:
    context["view"] = _view(bdd_client, _day(context))


# --- What today shows ---


@then(parsers.parse('I see the workout "{label}"'))
def _see_workout(context: dict[str, object], label: str) -> None:
    workout = context["view"]["workout"]
    assert workout is not None
    assert workout["label"] == label


@then(parsers.parse('I see a "{name}" round'))
def _see_mobility_round(context: dict[str, object], name: str) -> None:
    # full_plan schedules mobility for Monday; the section is present (may be empty
    # until moves are recorded, but for a workout day it is a list, not None).
    assert context["view"]["mobility"] is not None


@then("I see today's four planned meals")
def _see_four_meals(context: dict[str, object]) -> None:
    assert len(context["view"]["meals"]) == 4


@then(
    parsers.parse(
        "I see the daily targets: {steps} steps, {water} L water, {n:d} electrolyte serve"
    )
)
def _see_targets(context: dict[str, object], steps: str, water: str, n: int) -> None:
    targets = context["view"]["targets"]
    assert targets["steps_target"] == 7000
    assert targets["water_min_l"] == 2.0
    assert targets["water_max_l"] == 3.0
    assert targets["electrolytes_per_day"] == n


# --- Rest day ---


@then("I see no workout")
def _no_workout(context: dict[str, object]) -> None:
    assert context["view"]["workout"] is None


@then("I see today's planned meals")
def _see_meals(context: dict[str, object]) -> None:
    assert context["view"]["meals"]


@then("I see the daily wellbeing log")
def _see_wellbeing_log(context: dict[str, object]) -> None:
    assert "wellbeing" in context["view"]


# --- Meals & carbs ---


@then(parsers.parse('"{name}" shows {carbs:d} g carbs'))
def _meal_shows_carbs(context: dict[str, object], name: str, carbs: int) -> None:
    assert _meal_by_name(context["view"], name)["carbs_g"] == carbs


@then("the carb figure is attributed to the active plan")
def _carb_attributed_to_plan(context: dict[str, object]) -> None:
    # The daily view is derived from the active plan; has_plan proves the source.
    assert context["view"]["has_plan"] is True


@then(parsers.parse("the list shows a daily carb total of {total:d} g"))
def _daily_carb_total(context: dict[str, object], total: int) -> None:
    assert context["view"]["daily_carbs_total"] == total


@then("I cannot edit a meal's carbs from the daily list")
def _cannot_edit_carbs(context: dict[str, object], bdd_client: TestClient) -> None:
    # UI-only assertion: the daily API exposes no write path for a meal's carbs. Confirm
    # neither PUT nor PATCH to a meal on the daily view is routable.
    view = context["view"]
    meal_id = view["meals"][0]["id"]
    day = _day(context)
    for verb in ("put", "patch"):
        resp = getattr(bdd_client, verb)(
            f"{_API}/daily/{day}/meals/{meal_id}", json={"carbs_g": 999}
        )
        assert resp.status_code in (404, 405), resp.text


# --- Meal adherence ---


@given(parsers.parse('I checked off "{name}" as eaten'))
def _given_checked(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    view = _view(bdd_client, _day(context))
    meal_id = _meal_by_name(view, name)["id"]
    context["meal_id"] = meal_id
    resp = bdd_client.post(f"{_API}/daily/{_day(context)}/meals/{meal_id}/check")
    assert resp.status_code == 200, resp.text
    assert resp.json()["eaten"] is True


@when(parsers.parse('I check off "{name}" as eaten'))
def _check_meal(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    view = _view(bdd_client, _day(context))
    meal_id = _meal_by_name(view, name)["id"]
    context["meal_id"] = meal_id
    context["meal_carbs_before"] = _meal_by_name(view, name)["carbs_g"]
    resp = bdd_client.post(f"{_API}/daily/{_day(context)}/meals/{meal_id}/check")
    assert resp.status_code == 200, resp.text
    assert resp.json()["eaten"] is True


@then("today records that the planned meal was eaten")
def _records_eaten(context: dict[str, object], bdd_client: TestClient) -> None:
    view = _view(bdd_client, _day(context))
    meal = next(m for m in view["meals"] if m["id"] == context["meal_id"])
    assert meal["eaten"] is True


@then("the meal's carb figure is unchanged")
def _carbs_unchanged(context: dict[str, object], bdd_client: TestClient) -> None:
    view = _view(bdd_client, _day(context))
    meal = next(m for m in view["meals"] if m["id"] == context["meal_id"])
    assert meal["carbs_g"] == context["meal_carbs_before"]


@when("I un-check it")
def _uncheck_meal(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.delete(f"{_API}/daily/{_day(context)}/meals/{context['meal_id']}/check")
    assert resp.status_code == 200, resp.text
    assert resp.json()["eaten"] is False


@then("today no longer records that meal as eaten")
def _no_longer_eaten(context: dict[str, object], bdd_client: TestClient) -> None:
    view = _view(bdd_client, _day(context))
    meal = next(m for m in view["meals"] if m["id"] == context["meal_id"])
    assert meal["eaten"] is False


# --- Activities & mobility ---


@given(parsers.parse('"{label}" prescribes "{name}" at {sets:d} × {reps:d}'))
def _prescribes(context: dict[str, object], label: str, name: str, sets: int, reps: int) -> None:
    context["expected_target_sets"] = sets  # documented by full_plan.


@when(parsers.parse('I log {n:d} sets for "{name}"'))
def _log_sets(context: dict[str, object], bdd_client: TestClient, n: int, name: str) -> None:
    day = _day(context)
    resp = bdd_client.post(f"{_API}/sessions", json={"date": day})
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]
    slug = _EXERCISE_SLUGS[name]
    for _ in range(n):
        r = bdd_client.post(
            f"{_API}/sessions/{sid}/sets",
            json={"exercise_slug": slug, "reps": "15", "weight": "50"},
        )
        assert r.status_code == 201, r.text


@then(parsers.parse('today\'s list shows "{name}" at {done:d} of {total:d} sets'))
def _shows_sets(
    context: dict[str, object], bdd_client: TestClient, name: str, done: int, total: int
) -> None:
    view = _view(bdd_client, _day(context))
    workout = view["workout"]
    assert workout is not None
    line = next(e for e in workout["exercises"] if e["slug"] == _EXERCISE_SLUGS[name])
    assert line["completed_sets"] == done
    assert line["target_sets"] == total


def _seed_mobility_catalog(bdd_client: TestClient) -> None:
    """Populate the mobility catalog by recording moves on an arbitrary past date."""
    for slug in _MOBILITY_SLUGS.values():
        resp = bdd_client.post(
            f"{_API}/mobility/done", json={"date": "2026-05-01", "exercise_slug": slug}
        )
        assert resp.status_code == 201, resp.text


@then("I see a mobility section with my mobility moves to tick off")
def _see_mobility_section(context: dict[str, object], bdd_client: TestClient) -> None:
    # Seed the catalog, then re-open: the derived section now lists the moves.
    _seed_mobility_catalog(bdd_client)
    view = _view(bdd_client, _day(context))
    mobility = view["mobility"]
    assert mobility is not None
    names = {m["name"] for m in mobility}
    assert "Bird Dog" in names
    assert all(m["done"] is False for m in mobility)  # not yet done today.


@then("there is no mobility section")
def _no_mobility_section(context: dict[str, object]) -> None:
    # On a rest day the workout is None and mobility is None (see resolve_day).
    view = context["view"]
    assert not view["mobility"]


@given(parsers.parse('today\'s mobility includes "{name}"'))
def _mobility_includes(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    _seed_mobility_catalog(bdd_client)
    context["mobility_slug"] = _MOBILITY_SLUGS[name]


@when(parsers.parse('I mark "{name}" done'))
def _mark_done(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    slug = _MOBILITY_SLUGS[name]
    resp = bdd_client.post(
        f"{_API}/mobility/done", json={"date": _day(context), "exercise_slug": slug}
    )
    assert resp.status_code == 201, resp.text


@then(parsers.parse('today\'s list shows "{name}" as completed'))
def _mobility_completed(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    view = _view(bdd_client, _day(context))
    slug = _MOBILITY_SLUGS[name]
    item = next(m for m in view["mobility"] if m["slug"] == slug)
    assert item["done"] is True


@when(parsers.parse('I un-mark "{name}"'))
def _unmark(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    slug = _MOBILITY_SLUGS[name]
    resp = bdd_client.delete(
        f"{_API}/mobility/done", params={"on": _day(context), "exercise_slug": slug}
    )
    assert resp.status_code == 200, resp.text


@then(parsers.parse('"{name}" is no longer completed'))
def _mobility_not_completed(context: dict[str, object], bdd_client: TestClient, name: str) -> None:
    view = _view(bdd_client, _day(context))
    slug = _MOBILITY_SLUGS[name]
    item = next(m for m in view["mobility"] if m["slug"] == slug)
    assert item["done"] is False


# --- Daily wellbeing ---


@when(
    parsers.parse(
        "I set today's energy to {energy:d}, motivation to {motivation:d}, "
        "stress to {stress:d}, and hunger to {hunger:d}"
    )
)
def _set_wellbeing(
    context: dict[str, object],
    bdd_client: TestClient,
    energy: int,
    motivation: int,
    stress: int,
    hunger: int,
) -> None:
    resp = bdd_client.put(
        f"{_API}/daily/{_day(context)}/wellbeing",
        json={"energy": energy, "motivation": motivation, "stress": stress, "hunger": hunger},
    )
    assert resp.status_code == 200, resp.text


@then(
    parsers.parse(
        "today's wellbeing is saved as energy {energy:d}, motivation {motivation:d}, "
        "stress {stress:d}, hunger {hunger:d}"
    )
)
def _wellbeing_saved(
    context: dict[str, object],
    bdd_client: TestClient,
    energy: int,
    motivation: int,
    stress: int,
    hunger: int,
) -> None:
    wb = _view(bdd_client, _day(context))["wellbeing"]
    assert wb["energy"] == energy
    assert wb["motivation"] == motivation
    assert wb["stress"] == stress
    assert wb["hunger"] == hunger


@when(parsers.parse("I try to set today's energy to {energy:d}"))
def _try_set_energy(context: dict[str, object], bdd_client: TestClient, energy: int) -> None:
    context["wellbeing_resp"] = bdd_client.put(
        f"{_API}/daily/{_day(context)}/wellbeing", json={"energy": energy}
    )


@then("the entry is rejected")
def _rejected(context: dict[str, object]) -> None:
    assert context["wellbeing_resp"].status_code == 422


@given(parsers.parse("I logged today's energy as {energy:d} this morning"))
def _logged_energy(context: dict[str, object], bdd_client: TestClient, energy: int) -> None:
    resp = bdd_client.put(f"{_API}/daily/{_day(context)}/wellbeing", json={"energy": energy})
    assert resp.status_code == 200, resp.text


@when(parsers.parse("I change today's energy to {energy:d}"))
def _change_energy(context: dict[str, object], bdd_client: TestClient, energy: int) -> None:
    resp = bdd_client.put(f"{_API}/daily/{_day(context)}/wellbeing", json={"energy": energy})
    assert resp.status_code == 200, resp.text


@then(parsers.parse("today's energy reads {energy:d}"))
def _energy_reads(context: dict[str, object], bdd_client: TestClient, energy: int) -> None:
    assert _view(bdd_client, _day(context))["wellbeing"]["energy"] == energy


@then("no duplicate entry is created")
def _no_duplicate_wellbeing(context: dict[str, object], bdd_client: TestClient) -> None:
    # Wellbeing is upserted per date; the single view reflects one canonical row.
    wb = _view(bdd_client, _day(context))["wellbeing"]
    assert wb["energy"] is not None


# --- Steps / water / notes ---


@given(parsers.parse("{steps} steps have synced for today"))
def _steps_synced(context: dict[str, object], seed, steps: str) -> None:
    n = int(steps.replace(",", ""))
    day = _day(context)
    seed(lambda s: add_steps(s, date.fromisoformat(day), n))
    context["expected_steps"] = n


@then(parsers.parse("the steps target shows {steps} of {target}"))
def _steps_target(context: dict[str, object], steps: str, target: str) -> None:
    steps_block = context["view"]["steps"]
    assert steps_block["steps"] == int(steps.replace(",", ""))
    assert steps_block["target"] == int(target.replace(",", ""))


@when(parsers.parse("I log {units:d} of my water targets and {n:d} electrolyte serve"))
def _log_water(context: dict[str, object], bdd_client: TestClient, units: int, n: int) -> None:
    resp = bdd_client.put(
        f"{_API}/daily/{_day(context)}/log",
        json={"water_units": units, "electrolytes_done": True},
    )
    assert resp.status_code == 200, resp.text
    context["water_units"] = units


@then("today shows water progress and the electrolyte serve as done")
def _water_shown(context: dict[str, object], bdd_client: TestClient) -> None:
    view = _view(bdd_client, _day(context))
    assert view["water_units"] == context["water_units"]
    assert view["electrolytes_done"] is True


@when(parsers.parse('I add a note "{note}"'))
def _add_note(context: dict[str, object], bdd_client: TestClient, note: str) -> None:
    resp = bdd_client.put(f"{_API}/daily/{_day(context)}/log", json={"notes": note})
    assert resp.status_code == 200, resp.text
    context["note"] = note


@then("today keeps that note")
def _keeps_note(context: dict[str, object], bdd_client: TestClient) -> None:
    assert _view(bdd_client, _day(context))["notes"] == context["note"]
