"""Execute features/mobility.feature via pytest-bdd (sync TestClient harness).

The mobility "round" for a day is the mobility list inside GET /daily/{day}. It is only
present on workout days and is derived from MobilityDone history (services/daily.py
_mobility_for). So the round's catalog is populated by ticking the moves off on an earlier
date; the Background does exactly that so 2026-05-22 (Friday, Training Day 3) shows all
three moves with done=false.
"""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.seed import full_plan

scenarios("mobility.feature")

_DAILY = "/api/v1/daily"
_DONE = "/api/v1/mobility/done"
_TODAY = "2026-05-22"  # a Friday -> Training Day 3 (workout day, has mobility)
_SEED_DATE = "2026-05-15"  # an earlier date used to populate the round's catalog

# Round move name -> exercise slug (matches seed.full_plan's exercise catalog).
_SLUGS = {
    "Bird Dog": "bird-dog",
    "Cat-Cow": "cat-cow",
    "Shoulder CARs": "shoulder-cars",
}


def _mobility(client: TestClient, day: str) -> list[dict]:
    resp = client.get(f"{_DAILY}/{day}")
    assert resp.status_code == 200, resp.text
    return resp.json()["mobility"]


def _mark(client: TestClient, name: str, day: str) -> None:
    resp = client.post(_DONE, json={"date": day, "exercise_slug": _SLUGS[name]})
    assert resp.status_code == 201, resp.text


# --- Background -------------------------------------------------------------


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given(parsers.parse("today is {d}"))
def _today(context: dict, d: str) -> None:
    context["today"] = d
    assert d == _TODAY  # the feature's fixed date; a Friday / workout day


@given(parsers.parse('today\'s plan includes a "Mobility" round with "{a}", "{b}" and "{c}"'))
def _plan_with_round(bdd_client: TestClient, seed, context: dict, a: str, b: str, c: str) -> None:
    # Seed the canonical active plan so 2026-05-22 (Friday) is Training Day 3 with mobility.
    seed(lambda s: full_plan(s, start=date(2026, 5, 21)))
    # A day's round is derived from MobilityDone history, so seed the catalog by ticking
    # each move off on an earlier date. That makes them appear (done=false) on 2026-05-22.
    for name in (a, b, c):
        _mark(bdd_client, name, _SEED_DATE)
    context["round"] = [a, b, c]

    items = _mobility(bdd_client, _TODAY)
    got = {i["name"] for i in items}
    assert got == {a, b, c}, got
    assert all(not i["done"] for i in items)  # none done yet on today


# --- Scenario: See today's mobility round -----------------------------------


@when("I open today's mobility")
def _open_today(bdd_client: TestClient, context: dict) -> None:
    context["items"] = _mobility(bdd_client, _TODAY)


@then(parsers.parse('I see "{a}", "{b}" and "{c}" to do'))
def _see_to_do(context: dict, a: str, b: str, c: str) -> None:
    names = {i["name"] for i in context["items"]}
    assert names == {a, b, c}, names


# --- Scenario: Mark a mobility exercise done --------------------------------


@when(parsers.re(r'I mark "(?P<name>[^"]+)" done$'))
def _mark_one(bdd_client: TestClient, name: str) -> None:
    _mark(bdd_client, name, _TODAY)


@then(parsers.parse('"{name}" is recorded as completed today'))
def _recorded_completed(bdd_client: TestClient, name: str) -> None:
    slug = _SLUGS[name]
    # The GET /mobility/done list for today includes it,
    done = bdd_client.get(_DONE, params={"on": _TODAY}).json()
    assert slug in done, done
    # and the day's round shows it done.
    item = next(i for i in _mobility(bdd_client, _TODAY) if i["name"] == name)
    assert item["done"] is True


@then(parsers.parse("today's mobility shows {n:d} of {total:d} done"))
def _shows_n_of_total(bdd_client: TestClient, n: int, total: int) -> None:
    items = _mobility(bdd_client, _TODAY)
    assert len(items) == total, items
    assert sum(1 for i in items if i["done"]) == n


# --- Scenario: Completing every exercise completes the round ----------------


@when(parsers.re(r'I mark "(?P<a>[^"]+)", "(?P<b>[^"]+)" and "(?P<c>[^"]+)" done$'))
def _mark_all(bdd_client: TestClient, a: str, b: str, c: str) -> None:
    for name in (a, b, c):
        _mark(bdd_client, name, _TODAY)


@then("today's mobility round is complete")
def _round_complete(bdd_client: TestClient) -> None:
    items = _mobility(bdd_client, _TODAY)
    assert items  # there is a round
    assert all(i["done"] for i in items)


# --- Scenario: An unmarked exercise is not counted --------------------------


@when(parsers.parse('I mark only "{name}" done'))
def _mark_only(bdd_client: TestClient, name: str) -> None:
    _mark(bdd_client, name, _TODAY)


@then(parsers.parse('"{b}" and "{c}" remain not done'))
def _remain_not_done(bdd_client: TestClient, b: str, c: str) -> None:
    items = {i["name"]: i["done"] for i in _mobility(bdd_client, _TODAY)}
    assert items[b] is False
    assert items[c] is False


# --- Scenario: Mobility completion counts toward the day's adherence --------


@given("I completed today's mobility round")
def _completed_round(bdd_client: TestClient, context: dict) -> None:
    for name in context["round"]:
        _mark(bdd_client, name, _TODAY)


@when("I view today's adherence")
def _view_adherence(bdd_client: TestClient, context: dict) -> None:
    context["items"] = _mobility(bdd_client, _TODAY)


@then("mobility shows as done")
def _mobility_done(context: dict) -> None:
    items = context["items"]
    assert items
    assert all(i["done"] for i in items)
