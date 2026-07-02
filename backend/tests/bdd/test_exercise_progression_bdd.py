"""Execute features/exercise_progression.feature via pytest-bdd.

Progression = the top set per workout day over time (oldest → newest), sharing the
locked "top set" rule with the last-week column: heaviest weight, ties → most reps;
bodyweight → best reps. History is aggregated across all sessions for a slug, so it
spans plan blocks. A never-logged slug 404s. The "grouped under workout day" and
chart scenarios assert against real endpoint data (charts are a UI concern, so those
steps assert the underlying series/grouping the UI would draw from).
"""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.seed import full_plan

scenarios("exercise_progression.feature")

_SLUGS = {
    "Leg Press Machine": "leg-press-machine",
    "Crunches": "crunches",
    "Hip Thrust": "hip-thrust",
}


def _progress(bdd_client: TestClient, slug: str):
    return bdd_client.get(f"/api/v1/exercises/{slug}/progress")


def _log_top_set(bdd_client: TestClient, slug: str, day: str, *, weight: str, reps: str) -> None:
    """Create (idempotent) a session for the date, then log one set for the slug."""
    resp = bdd_client.post("/api/v1/sessions", json={"date": day})
    assert resp.status_code in (200, 201), resp.text
    session_id = resp.json()["id"]
    r = bdd_client.post(
        f"/api/v1/sessions/{session_id}/sets",
        json={"exercise_slug": slug, "weight": weight, "reps": reps},
    )
    assert r.status_code == 201, r.text


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given(parsers.parse('I have logged "{name}" across several sessions'))
def _logged_weighted(bdd_client: TestClient, name: str) -> None:
    slug = _SLUGS[name]
    if slug == "crunches":
        # bodyweight: no weight, increasing reps
        for day, reps in (("2026-05-25", "12"), ("2026-06-01", "15"), ("2026-06-08", "18")):
            _log_top_set(bdd_client, slug, day, weight="", reps=reps)
    else:
        # weighted: increasing top-set weight across three past dates
        for day, wt in (("2026-05-25", "50"), ("2026-06-01", "55"), ("2026-06-08", "60")):
            _log_top_set(bdd_client, slug, day, weight=wt, reps="15")


@given(parsers.parse('I have logged "{name}" (bodyweight) across several sessions'))
def _logged_bodyweight(bdd_client: TestClient, name: str) -> None:
    slug = _SLUGS[name]
    for day, reps in (("2026-05-25", "12"), ("2026-06-01", "15"), ("2026-06-08", "18")):
        _log_top_set(bdd_client, slug, day, weight="", reps=reps)


@given(parsers.parse('I logged "{name}" under the plan dated {d}'))
def _logged_under_plan(bdd_client: TestClient, name: str, d: str) -> None:
    # A session logged shortly after that plan's start date. The progress endpoint
    # aggregates by slug regardless of which plan block the session falls in.
    slug = _SLUGS[name]
    _log_top_set(bdd_client, slug, d, weight="50", reps="15")


@given(parsers.parse("I logged it again under the plan dated {d}"))
def _logged_again_under_plan(bdd_client: TestClient, d: str) -> None:
    _log_top_set(bdd_client, "leg-press-machine", d, weight="60", reps="15")


@given(parsers.parse('I have never logged "{name}"'))
def _never_logged(name: str) -> None:
    pass  # nothing is seeded for this slug


@given("my current plan has training days each with their exercises")
def _plan_with_days(seed) -> None:
    seed(lambda s: full_plan(s, start=date(2026, 5, 21)))


@when(parsers.parse('I view the "{name}" progression'))
@when(parsers.parse('I select "{name}"'))
def _view_progression(bdd_client: TestClient, context: dict, name: str) -> None:
    context["name"] = name
    context["resp"] = _progress(bdd_client, _SLUGS[name])


@when("I open the exercise progress area")
def _open_progress_area(bdd_client: TestClient, context: dict) -> None:
    context["resp"] = bdd_client.get("/api/v1/plans/current/detail")


@then("I see its top set for each session date, oldest to newest")
def _top_set_each_date(context: dict) -> None:
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["slug"] == "leg-press-machine"
    assert body["metric"] == "weight"
    points = body["points"]
    dates = [p["date"] for p in points]
    assert dates == sorted(dates)  # oldest -> newest
    assert dates == ["2026-05-25", "2026-06-01", "2026-06-08"]
    # each point carries the top-set weight and a rendered display
    assert [p["weight"] for p in points] == [50.0, 55.0, 60.0]
    assert all(p["display"] for p in points)


@then("I see the top-set reps for each session date")
def _top_reps_each_date(context: dict) -> None:
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["slug"] == "crunches"
    assert body["metric"] == "reps"  # bodyweight -> reps series
    points = body["points"]
    dates = [p["date"] for p in points]
    assert dates == sorted(dates)
    assert [p["reps"] for p in points] == [12, 15, 18]
    assert all(p["weight"] is None for p in points)


@then("I see sessions from both plans in one continuous history")
def _both_plans(context: dict) -> None:
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    points = resp.json()["points"]
    dates = [p["date"] for p in points]
    # both the 2026-05-21 and 2026-07-02 sessions appear, oldest -> newest
    assert "2026-05-21" in dates
    assert "2026-07-02" in dates
    assert dates == sorted(dates)


@then("I see that there is no history yet")
def _no_history(context: dict) -> None:
    # never-logged exercise -> 404 (no history)
    assert context["resp"].status_code == 404


@then("the exercises are listed grouped under their workout day")
def _grouped_under_day(context: dict) -> None:
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    training_days = resp.json()["training_days"]
    assert training_days
    for td in training_days:
        assert td["label"]
        assert td["exercises"]  # each workout day groups its exercises
        assert all(e["slug"] and e["name"] for e in td["exercises"])
    # sanity: Leg Press Machine sits under a training day
    all_slugs = {e["slug"] for td in training_days for e in td["exercises"]}
    assert "leg-press-machine" in all_slugs


@then("I see a chart of its top weight per workout day over time")
def _weight_chart(context: dict) -> None:
    # UI draws the chart; assert the underlying weight series it plots.
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric"] == "weight"
    weights = [p["weight"] for p in body["points"]]
    assert all(w is not None for w in weights)
    assert len(weights) >= 2  # enough points to plot a trend


@then("I see a chart of its best reps per workout day over time")
def _reps_chart(context: dict) -> None:
    resp = context["resp"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["metric"] == "reps"
    reps = [p["reps"] for p in body["points"]]
    assert all(r is not None for r in reps)
    assert len(reps) >= 2
