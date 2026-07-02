"""Execute features/workout_logging.feature via pytest-bdd (sync TestClient harness).

Contract exercised (all /api/v1):
  POST /sessions {date, training_day_id?}      -> idempotent per date, 201, {id, date, sets}
  POST /sessions/{id}/sets {exercise_slug, ...} -> 201, {id, set_index, reps, weight, display}
  PATCH /sets/{id} {reps, weight}               -> updated SetRead
  DELETE /sets/{id}                             -> 204
  GET  /sessions                                -> history (newest first, empty excluded)
  GET  /sessions/by-date/{day}                  -> SessionRead | null
  GET  /exercises/{slug}/last-week?before=DATE  -> {display}  ("N kg" / "BW" / "—")
  GET  /daily/{day}                             -> workout.exercises[].completed_sets/target_sets
"""

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.seed import full_plan

scenarios("workout_logging.feature")

_API = "/api/v1"
TODAY = "2026-05-25"

# Map the human exercise names used in the feature to canonical slugs.
_SLUGS = {
    "Leg Press Machine": "leg-press-machine",
    "Lat Pulldown": "lat-pulldown",
    "Seated Pulley Row": "seated-pulley-row",
    "Crunches": "crunches",
    "Hip Thrust": "hip-thrust",  # deliberately un-seeded: "no prior history" case
}


def _slug(name: str) -> str:
    return _SLUGS[name]


def _session_id(client: TestClient, date: str, training_day_id: int | None = None) -> int:
    """POST /sessions is idempotent per date; return the (stable) session id."""
    body: dict[str, object] = {"date": date}
    if training_day_id is not None:
        body["training_day_id"] = training_day_id
    resp = client.post(f"{_API}/sessions", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _log_set(client: TestClient, sid: int, slug: str, reps: str, weight: str) -> dict[str, object]:
    resp = client.post(
        f"{_API}/sessions/{sid}/sets",
        json={"exercise_slug": slug, "reps": reps, "weight": weight},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------------------- #
# Background
# --------------------------------------------------------------------------- #


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given(parsers.parse("today is {day}"))
def _today(context: dict[str, object], day: str) -> None:
    # The suite has no clock override; the fixed date is threaded through explicitly.
    assert day == TODAY
    context["today"] = day


@given(parsers.parse('today\'s scheduled session is "{label}"'))
def _scheduled(seed, context: dict[str, object], label: str) -> None:
    # full_plan seeds Training Day 1 (Mon) with the leg-press prescription and last-week
    # resolution against the canonical exercise catalog.
    plan = seed(full_plan)
    context["plan_label"] = label
    context["plan"] = plan


@given(parsers.parse('"{label}" prescribes "{name}" at {sets:d} × {reps:d}'))
def _prescribes(context: dict[str, object], label: str, name: str, sets: int, reps: int) -> None:
    # Documented by full_plan; assert it surfaces via the daily workout block.
    context["expected_target_sets"] = sets


# --------------------------------------------------------------------------- #
# Log a resistance set
# --------------------------------------------------------------------------- #


@when(parsers.parse('I log a set for "{name}" of {weight:d} kg × {reps:d} reps'))
def _log_resistance(
    context: dict[str, object], bdd_client: TestClient, name: str, weight: int, reps: int
) -> None:
    sid = _session_id(bdd_client, TODAY)
    context["session_id"] = sid
    context["last_set"] = _log_set(bdd_client, sid, _slug(name), str(reps), str(weight))
    context["last_slug"] = _slug(name)


@then("the set is saved against today's session")
def _saved_today(context: dict[str, object], bdd_client: TestClient) -> None:
    sid = context["session_id"]
    resp = bdd_client.get(f"{_API}/sessions/by-date/{TODAY}")
    assert resp.status_code == 200
    body = resp.json()
    assert body is not None
    assert body["id"] == sid
    assert any(s["id"] == context["last_set"]["id"] for s in body["sets"])


@then(parsers.parse('"{name}" shows {done:d} of {total:d} sets completed'))
def _shows_completed(bdd_client: TestClient, name: str, done: int, total: int) -> None:
    resp = bdd_client.get(f"{_API}/daily/{TODAY}")
    assert resp.status_code == 200
    workout = resp.json()["workout"]
    assert workout is not None
    line = next(e for e in workout["exercises"] if e["slug"] == _slug(name))
    assert line["completed_sets"] == done
    assert line["target_sets"] == total


# --------------------------------------------------------------------------- #
# Log a bodyweight set (no weight)
# --------------------------------------------------------------------------- #


@given(parsers.parse('"{name}" is a bodyweight exercise'))
def _is_bodyweight(name: str) -> None:
    pass  # seeded via full_plan (crunches -> is_bodyweight True)


@when(parsers.parse('I log a set for "{name}" of {reps:d} reps with no weight'))
def _log_bodyweight(
    context: dict[str, object], bdd_client: TestClient, name: str, reps: int
) -> None:
    sid = _session_id(bdd_client, TODAY)
    context["session_id"] = sid
    context["last_set"] = _log_set(bdd_client, sid, _slug(name), str(reps), "")


@then("the set is saved with an empty weight")
def _empty_weight(context: dict[str, object]) -> None:
    assert context["last_set"]["weight"] == ""


@then(parsers.parse('the set is displayed as "{display}"'))
def _displayed_as(context: dict[str, object], display: str) -> None:
    assert context["last_set"]["display"] == display


# --------------------------------------------------------------------------- #
# Edit a logged set
# --------------------------------------------------------------------------- #


@given(parsers.parse('I logged "{name}" of {weight:d} kg × {reps:d} reps'))
def _given_logged(
    context: dict[str, object], bdd_client: TestClient, name: str, weight: int, reps: int
) -> None:
    sid = _session_id(bdd_client, TODAY)
    context["session_id"] = sid
    context["last_set"] = _log_set(bdd_client, sid, _slug(name), str(reps), str(weight))
    context["last_slug"] = _slug(name)


@when(parsers.parse("I change that set to {weight:d} kg × {reps:d} reps"))
def _change_set(context: dict[str, object], bdd_client: TestClient, weight: int, reps: int) -> None:
    set_id = context["last_set"]["id"]
    resp = bdd_client.patch(
        f"{_API}/sets/{set_id}", json={"reps": str(reps), "weight": str(weight)}
    )
    assert resp.status_code == 200, resp.text
    context["last_set"] = resp.json()


@then(parsers.parse("the set reads {weight:d} kg × {reps:d} reps"))
def _set_reads(context: dict[str, object], weight: int, reps: int) -> None:
    assert context["last_set"]["display"] == f"{weight} kg × {reps}"


@then("no extra set is created")
def _no_extra_set(context: dict[str, object], bdd_client: TestClient) -> None:
    body = bdd_client.get(f"{_API}/sessions/by-date/{TODAY}").json()
    matching = [s for s in body["sets"] if s["exercise_slug"] == context["last_slug"]]
    assert len(matching) == 1


# --------------------------------------------------------------------------- #
# Delete a logged set
# --------------------------------------------------------------------------- #


@given(parsers.parse('I have logged {n:d} sets for "{name}"'))
def _logged_n_sets(context: dict[str, object], bdd_client: TestClient, n: int, name: str) -> None:
    sid = _session_id(bdd_client, TODAY)
    context["session_id"] = sid
    slug = _slug(name)
    context["last_slug"] = slug
    context["set_ids"] = [_log_set(bdd_client, sid, slug, "15", "40")["id"] for _ in range(n)]


@when("I delete the second set")
def _delete_second(context: dict[str, object], bdd_client: TestClient) -> None:
    set_ids = context["set_ids"]
    resp = bdd_client.delete(f"{_API}/sets/{set_ids[1]}")
    assert resp.status_code == 204, resp.text


# --------------------------------------------------------------------------- #
# Last-week column (headline feature)
# --------------------------------------------------------------------------- #


@given(parsers.parse('I logged "{name}" on {day}, heaviest set {weight:d} kg'))
def _logged_prior_heaviest(bdd_client: TestClient, name: str, day: str, weight: int) -> None:
    sid = _session_id(bdd_client, day)
    slug = _slug(name)
    # A lighter set plus the heaviest, to prove "heaviest wins".
    _log_set(bdd_client, sid, slug, "15", str(weight - 5))
    _log_set(bdd_client, sid, slug, "12", str(weight))


@given('I have not trained "Lat Pulldown" since')
def _not_trained_since() -> None:
    pass  # nothing else logged for the slug; the query returns the single prior date


@given(parsers.parse('on {day} I logged these sets for "{name}":'))
def _logged_prior_table(
    bdd_client: TestClient, day: str, name: str, datatable: list[list[str]]
) -> None:
    sid = _session_id(bdd_client, day)
    slug = _slug(name)
    for weight, reps in datatable[1:]:  # skip header row
        _log_set(bdd_client, sid, slug, reps, weight)


@given(parsers.parse('I logged "{name}" (bodyweight) on {day}'))
def _logged_prior_bodyweight(bdd_client: TestClient, name: str, day: str) -> None:
    sid = _session_id(bdd_client, day)
    _log_set(bdd_client, sid, _slug(name), "15", "")


@given(parsers.parse('I have never logged "{name}"'))
def _never_logged(name: str) -> None:
    pass  # slug is intentionally absent from any session


@given(parsers.parse("I have already logged {weight:d} kg earlier in today's session"))
def _logged_today_earlier(bdd_client: TestClient, weight: int) -> None:
    sid = _session_id(bdd_client, TODAY)
    _log_set(bdd_client, sid, _slug("Leg Press Machine"), "15", str(weight))


@when("I open today's session")
@when(parsers.parse('I view the "last week" column for "{name}"'))
def _open_today() -> None:
    pass  # last-week is read per-exercise in the Then step


@then(parsers.parse('the "last week" column for "{name}" shows "{display}"'))
@then(parsers.parse('it still shows "{display}"'))
def _last_week_shows(
    context: dict[str, object],
    bdd_client: TestClient,
    name: str = "Leg Press Machine",
    display: str = "",
) -> None:
    slug = _slug(name)
    resp = bdd_client.get(f"{_API}/exercises/{slug}/last-week", params={"before": TODAY})
    assert resp.status_code == 200, resp.text
    assert resp.json()["display"] == display


# --------------------------------------------------------------------------- #
# Workout history
# --------------------------------------------------------------------------- #


@given("I logged workouts on several days")
def _logged_several_days(context: dict[str, object], bdd_client: TestClient) -> None:
    days = ["2026-05-11", "2026-05-18", TODAY]
    for day in days:
        sid = _session_id(bdd_client, day)
        _log_set(bdd_client, sid, _slug("Leg Press Machine"), "15", "40")
    # An empty session that must be excluded from history.
    _session_id(bdd_client, "2026-05-04")
    context["logged_days"] = days
    context["empty_day"] = "2026-05-04"


@when("I open my workout history")
def _open_history(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_API}/sessions")
    assert resp.status_code == 200
    context["history"] = resp.json()


@then("I see each logged day with its exercises and sets, most recent first")
def _history_ordered(context: dict[str, object]) -> None:
    history = context["history"]
    dates = [row["date"] for row in history]
    # Newest first.
    assert dates == sorted(dates, reverse=True)
    for row in history:
        assert row["exercises"]
        assert row["exercises"][0]["sets"]


@then("days with no logged sets are not shown")
def _history_excludes_empty(context: dict[str, object]) -> None:
    dates = [row["date"] for row in context["history"]]
    assert context["empty_day"] not in dates


# --------------------------------------------------------------------------- #
# One workout per day / resume
# --------------------------------------------------------------------------- #


@when("I start today's workout")
def _start_workout(context: dict[str, object], bdd_client: TestClient) -> None:
    context["first_start_id"] = _session_id(bdd_client, TODAY)


@when("I start today's workout again")
def _start_workout_again(context: dict[str, object], bdd_client: TestClient) -> None:
    context["second_start_id"] = _session_id(bdd_client, TODAY)


@then("both refer to the same session for today")
def _same_session(context: dict[str, object]) -> None:
    assert context["first_start_id"] == context["second_start_id"]


@given(parsers.parse('I logged {n:d} sets for "{name}" today'))
def _logged_n_today(context: dict[str, object], bdd_client: TestClient, n: int, name: str) -> None:
    sid = _session_id(bdd_client, TODAY)
    slug = _slug(name)
    context["resume_slug"] = slug
    for _ in range(n):
        _log_set(bdd_client, sid, slug, "15", "40")


@when("I reload today's workout")
def _reload_workout(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_API}/sessions/by-date/{TODAY}")
    assert resp.status_code == 200
    context["reloaded"] = resp.json()


@then(parsers.parse('today\'s session still shows {n:d} logged sets for "{name}"'))
def _still_shows_sets(context: dict[str, object], n: int, name: str) -> None:
    body = context["reloaded"]
    assert body is not None
    slug = _slug(name)
    matching = [s for s in body["sets"] if s["exercise_slug"] == slug]
    assert len(matching) == n
