"""Execute features/weekly_checkin.feature via pytest-bdd (sync TestClient harness).

The weekly check-in assembles the last 7 days (rolling window ending on the start date)
into the PT package: latest body measurements, the four daily /10 metrics (values +
average over LOGGED days only), recovery context (steps / sleep), sessions logged, and a
place for posed photos and two free-text reflections. Glucose/insulin are deliberately
excluded from the package.

Background start date is 2026-05-25 -> window 2026-05-19..2026-05-25 (inclusive).
"""

from collections.abc import Callable, Coroutine
from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from tests.bdd.seed import add_glucose, add_insulin, add_sleep, add_steps

scenarios("weekly_checkin.feature")

_CI = "/api/v1/check-ins"
_M = "/api/v1/measurements"
_DAILY = "/api/v1/daily"

WINDOW = [date(2026, 5, d) for d in range(19, 26)]  # 2026-05-19 .. 2026-05-25
START = "2026-05-25"

# The `seed` fixture is a runner: seed(fn) executes async fn(session) and commits.
SeedFn = Callable[[AsyncSession], Coroutine[Any, Any, Any]]
SeedRunner = Callable[[SeedFn], Any]


def _view(context: dict[str, object]) -> dict[str, Any]:
    """The last-assembled check-in payload, typed for mypy."""
    view = context["view"]
    assert isinstance(view, dict)
    return view


# --- Background -----------------------------------------------------------------------


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given(parsers.parse("I start a weekly check-in on {d}"))
def _bg_start(context: dict[str, object], d: str) -> None:
    # Record the intended start date; the actual POST happens in the "When" step so that
    # seed data set up by intervening "Given" steps lands inside the window first.
    context["started_on"] = d


def _start_check_in(bdd_client: TestClient, context: dict[str, object]) -> dict[str, Any]:
    resp = bdd_client.post(_CI, json={"started_on": context["started_on"]})
    assert resp.status_code == 201, resp.text
    view: dict[str, Any] = resp.json()
    context["view"] = view
    context["check_in_id"] = view["id"]
    return view


@when("I start the weekly check-in")
def _when_start(bdd_client: TestClient, context: dict[str, object]) -> None:
    _start_check_in(bdd_client, context)


@when("I assemble the check-in")
def _when_assemble(bdd_client: TestClient, context: dict[str, object]) -> None:
    _start_check_in(bdd_client, context)


# --- Scenario: gathers the last 7 days ------------------------------------------------


@then("it collects the relevant data from the 7 days ending today")
def _collects_window(context: dict[str, object]) -> None:
    view = _view(context)
    assert view["started_on"] == START
    # The rolling window is present and the assembled package has the expected sections.
    for key in ("measurements", "latest_measurements", "metrics", "steps_avg", "sleep"):
        assert key in view


@then(parsers.parse("the window is {start} to {end}"))
def _window_bounds(context: dict[str, object], start: str, end: str) -> None:
    view = _view(context)
    assert view["window_start"] == start
    assert view["window_end"] == end


# --- Scenario: assemble what my PT asks for -------------------------------------------


@then("it includes my latest body measurements")
def _includes_measurements(context: dict[str, object]) -> None:
    view = _view(context)
    assert "measurements" in view
    assert "latest_measurements" in view
    assert set(view["latest_measurements"]) == {
        "waist_cm",
        "tummy_cm",
        "bum_cm",
        "right_thigh_cm",
        "left_thigh_cm",
        "weight_kg",
    }


@then("the last 7 days of energy, motivation, stress and hunger")
def _includes_metrics(context: dict[str, object]) -> None:
    metrics = _view(context)["metrics"]
    for name in ("energy", "motivation", "stress", "hunger"):
        assert name in metrics
        assert "values" in metrics[name]
        assert "average" in metrics[name]


@then("a place for posed photos")
def _place_for_photos(context: dict[str, object]) -> None:
    assert _view(context)["photos"] == []


@then(parsers.parse('fields for "{worked}" and "{struggles}"'))
def _reflection_fields(context: dict[str, object], worked: str, struggles: str) -> None:
    view = _view(context)
    assert "worked_on" in view
    assert "struggles" in view


# --- Scenario: /10 metrics show values + average --------------------------------------


@given("I logged daily energy, motivation, stress and hunger over the last 7 days")
def _log_all_days(bdd_client: TestClient, context: dict[str, object]) -> None:
    for i, day in enumerate(WINDOW):
        body = {
            "energy": 5 + (i % 3),
            "motivation": 6,
            "stress": 4,
            "hunger": 3,
        }
        assert bdd_client.put(f"{_DAILY}/{day}/wellbeing", json=body).status_code == 200
    context["logged_days"] = [d.isoformat() for d in WINDOW]


@then("I see each metric's daily values across those 7 days")
def _daily_values(context: dict[str, object]) -> None:
    metrics = _view(context)["metrics"]
    logged = context["logged_days"]
    for name in ("energy", "motivation", "stress", "hunger"):
        values = metrics[name]["values"]
        assert len(values) == 7
        assert [v["date"] for v in values] == logged


@then("a 7-day average for each metric")
def _seven_day_average(context: dict[str, object]) -> None:
    metrics = _view(context)["metrics"]
    for name in ("energy", "motivation", "stress", "hunger"):
        values = metrics[name]["values"]
        nums = [v["value"] for v in values]
        expected = round(sum(nums) / len(nums), 1)
        assert metrics[name]["average"] == expected


# --- Scenario: measurements pre-fill --------------------------------------------------


@given(parsers.parse("I recorded measurements on {d}"))
def _recorded_measurements(bdd_client: TestClient, context: dict[str, object], d: str) -> None:
    body = {
        "date": d,
        "waist_cm": 95.0,
        "tummy_cm": 97.0,
        "bum_cm": 100.0,
        "right_thigh_cm": 55.0,
        "left_thigh_cm": 55.5,
        "weight_kg": 88.0,
    }
    assert bdd_client.post(_M, json=body).status_code == 200
    context["recorded"] = body


@then("those measurements are pre-filled")
def _measurements_prefilled(context: dict[str, object]) -> None:
    recorded = context["recorded"]
    assert isinstance(recorded, dict)
    m = _view(context)["measurements"]
    assert m is not None
    assert m["date"] == recorded["date"]
    assert m["waist_cm"] == recorded["waist_cm"]
    assert m["weight_kg"] == recorded["weight_kg"]


# --- Scenario: last recorded value for every metric -----------------------------------


@given("I last recorded each body metric on various recent dates")
def _various_dates(bdd_client: TestClient, context: dict[str, object]) -> None:
    # Each metric last touched on a different in-window date; latest_per_metric should
    # surface the most recent non-null value for each, even from different rows.
    assert (
        bdd_client.post(
            _M, json={"date": "2026-05-20", "waist_cm": 99.0, "tummy_cm": 98.0}
        ).status_code
        == 200
    )
    assert (
        bdd_client.post(
            _M, json={"date": "2026-05-22", "bum_cm": 101.0, "right_thigh_cm": 56.0}
        ).status_code
        == 200
    )
    assert (
        bdd_client.post(
            _M,
            json={"date": "2026-05-24", "left_thigh_cm": 57.0, "weight_kg": 90.0, "waist_cm": 96.0},
        ).status_code
        == 200
    )
    context["expected_latest"] = {
        "waist_cm": 96.0,  # from 2026-05-24, newer than 2026-05-20
        "tummy_cm": 98.0,  # only on 2026-05-20
        "bum_cm": 101.0,
        "right_thigh_cm": 56.0,
        "left_thigh_cm": 57.0,
        "weight_kg": 90.0,
    }


@then(
    parsers.parse("I see the most recent value for each metric (waist, tummy, bum, thighs, weight)")
)
def _latest_per_metric(context: dict[str, object]) -> None:
    latest = _view(context)["latest_measurements"]
    expected = context["expected_latest"]
    assert isinstance(expected, dict)
    for metric, value in expected.items():
        assert latest[metric] == value, f"{metric}: {latest[metric]} != {value}"


# --- Scenario: recovery context -------------------------------------------------------


@given("steps and sleep synced over the last 7 days")
def _steps_sleep_synced(seed: SeedRunner, context: dict[str, object]) -> None:
    step_values = [7000, 7200, 6800, 8000, 5000, 9000, 7500]

    async def _seed(s: AsyncSession) -> None:
        for day, steps in zip(WINDOW, step_values, strict=True):
            await add_steps(s, day, steps)
            await add_sleep(s, day, with_stages=True)

    seed(_seed)
    context["step_values"] = step_values


@then("I see my average steps per day")
def _avg_steps(context: dict[str, object]) -> None:
    steps = context["step_values"]
    assert isinstance(steps, list)
    expected = round(sum(steps) / len(steps))
    assert _view(context)["steps_avg"] == expected


@then("my average sleep duration and efficiency for the window")
def _avg_sleep(context: dict[str, object]) -> None:
    sleep = _view(context)["sleep"]
    # add_sleep writes asleep_min=420, efficiency=93 for each of the 7 nights.
    assert sleep["nights"] == 7
    assert sleep["avg_asleep_min"] == 420
    assert sleep["avg_efficiency"] == 93.0


# --- Scenario: enter today's measurements from the check-in ---------------------------


@when("I fill in today's measurements grid and save")
def _fill_measurements(bdd_client: TestClient, context: dict[str, object]) -> None:
    # Start the check-in first so we can prove the values update on re-fetch.
    _start_check_in(bdd_client, context)
    body = {
        "date": START,
        "waist_cm": 94.0,
        "tummy_cm": 96.0,
        "bum_cm": 99.0,
        "right_thigh_cm": 54.0,
        "left_thigh_cm": 54.0,
        "weight_kg": 87.0,
    }
    assert bdd_client.post(_M, json=body).status_code == 200
    context["saved"] = body


@then("today's measurements are recorded")
def _recorded_today(bdd_client: TestClient, context: dict[str, object]) -> None:
    row = bdd_client.get(f"{_M}/{START}").json()
    saved = context["saved"]
    assert isinstance(saved, dict)
    assert row["waist_cm"] == saved["waist_cm"]


@then("the check-in's last-measurement values update")
def _checkin_updates(bdd_client: TestClient, context: dict[str, object]) -> None:
    view: dict[str, Any] = bdd_client.get(f"{_CI}/{context['check_in_id']}").json()
    saved = context["saved"]
    assert isinstance(saved, dict)
    assert view["measurements"]["waist_cm"] == saved["waist_cm"]
    assert view["latest_measurements"]["weight_kg"] == saved["weight_kg"]


# --- Scenario: attach posed photos ----------------------------------------------------


@when("I add posed photos")
def _add_photos(bdd_client: TestClient, context: dict[str, object]) -> None:
    _start_check_in(bdd_client, context)
    cid = context["check_in_id"]
    for name in ("front.jpg", "side.jpg"):
        resp = bdd_client.post(
            f"{_CI}/{cid}/photos",
            files={"file": (name, b"fakejpegbytes", "image/jpeg")},
        )
        assert resp.status_code == 201, resp.text
    context["photo_count"] = 2


@then("they are saved with this check-in")
def _photos_saved(bdd_client: TestClient, context: dict[str, object]) -> None:
    view: dict[str, Any] = bdd_client.get(f"{_CI}/{context['check_in_id']}").json()
    assert len(view["photos"]) == context["photo_count"]
    for photo in view["photos"]:
        assert photo["content_type"] == "image/jpeg"


# --- Scenario: a past check-in keeps its photos ---------------------------------------


@given("a completed check-in from a previous week with photos")
def _past_checkin_with_photos(bdd_client: TestClient, context: dict[str, object]) -> None:
    resp = bdd_client.post(_CI, json={"started_on": "2026-05-18"})
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]
    add = bdd_client.post(
        f"{_CI}/{cid}/photos",
        files={"file": ("past.jpg", b"pastbytes", "image/jpeg")},
    )
    assert add.status_code == 201, add.text
    finish = bdd_client.post(f"{_CI}/{cid}/finish")
    assert finish.status_code == 200, finish.text
    assert finish.json()["completed"] is True
    context["past_check_in_id"] = cid


@when("I open that past check-in")
def _open_past(bdd_client: TestClient, context: dict[str, object]) -> None:
    resp = bdd_client.get(f"{_CI}/{context['past_check_in_id']}")
    assert resp.status_code == 200
    context["past_view"] = resp.json()


@then("its photos are still viewable")
def _past_photos_viewable(context: dict[str, object]) -> None:
    view = context["past_view"]
    assert isinstance(view, dict)
    assert view["completed"] is True
    assert len(view["photos"]) == 1
    assert view["photos"][0]["content_type"] == "image/jpeg"


# --- Scenario: reflections with context -----------------------------------------------


@then("I see the last 7 days of logged sessions and adherence as context")
def _sessions_context(bdd_client: TestClient, context: dict[str, object], seed: SeedRunner) -> None:
    # sessions_logged counts Session rows in the window; seed two, re-fetch, assert.
    async def _seed(s: AsyncSession) -> None:
        s.add_all([Session(date=date(2026, 5, 20)), Session(date=date(2026, 5, 23))])

    seed(_seed)
    view: dict[str, Any] = bdd_client.get(f"{_CI}/{context['check_in_id']}").json()
    assert view["sessions_logged"] == 2


@then('I can write "what I worked on" and "struggles" freely')
def _write_reflections(bdd_client: TestClient, context: dict[str, object]) -> None:
    cid = context["check_in_id"]
    resp = bdd_client.patch(
        f"{_CI}/{cid}",
        json={"worked_on": "shoulder stability", "struggles": "sleep was poor midweek"},
    )
    assert resp.status_code == 200, resp.text
    view: dict[str, Any] = bdd_client.get(f"{_CI}/{cid}").json()
    assert view["worked_on"] == "shoulder stability"
    assert view["struggles"] == "sleep was poor midweek"


# --- Scenario: only photos and reflections need manual input --------------------------


@given("measurements and daily /10s are already captured for the last 7 days")
def _prefill_everything(
    bdd_client: TestClient, context: dict[str, object], seed: SeedRunner
) -> None:
    assert (
        bdd_client.post(_M, json={"date": START, "waist_cm": 95.0, "weight_kg": 88.0}).status_code
        == 200
    )
    for day in WINDOW:
        assert (
            bdd_client.put(
                f"{_DAILY}/{day}/wellbeing",
                json={"energy": 7, "motivation": 6, "stress": 4, "hunger": 3},
            ).status_code
            == 200
        )

    async def _seed(s: AsyncSession) -> None:
        for day in WINDOW:
            await add_steps(s, day, 7500)
            await add_sleep(s, day, with_stages=True)

    seed(_seed)


@then("everything else is pre-filled")
def _everything_prefilled(context: dict[str, object]) -> None:
    view = _view(context)
    assert view["measurements"] is not None
    assert all(v["values"] for v in view["metrics"].values())
    assert view["steps_avg"] is not None
    assert view["sleep"]["nights"] == 7


@then("only photos and the two reflections remain for me to add")
def _only_manual_left(context: dict[str, object]) -> None:
    view = _view(context)
    # Photos and reflections start empty; everything else is populated.
    assert view["photos"] == []
    assert view["worked_on"] is None
    assert view["struggles"] is None


# --- Scenario: missing days shown honestly --------------------------------------------


@given("I did not log wellbeing on some of the last 7 days")
def _partial_logging(bdd_client: TestClient, context: dict[str, object]) -> None:
    # Log only 3 of the 7 days; the other 4 stay unlogged (not zero).
    logged = [date(2026, 5, 19), date(2026, 5, 21), date(2026, 5, 25)]
    values = {date(2026, 5, 19): 4, date(2026, 5, 21): 6, date(2026, 5, 25): 8}
    for day in logged:
        assert (
            bdd_client.put(
                f"{_DAILY}/{day}/wellbeing",
                json={"energy": values[day], "motivation": 5, "stress": 5, "hunger": 5},
            ).status_code
            == 200
        )
    context["logged_days"] = [d.isoformat() for d in logged]
    context["energy_values"] = [values[d] for d in logged]


@then("the values and average reflect only the days I actually logged")
def _only_logged(context: dict[str, object]) -> None:
    energy = _view(context)["metrics"]["energy"]
    nums = context["energy_values"]
    assert isinstance(nums, list)
    assert [v["date"] for v in energy["values"]] == context["logged_days"]
    assert [v["value"] for v in energy["values"]] == nums
    assert energy["average"] == round(sum(nums) / len(nums), 1)


@then("the missing days are shown as missing, not counted as zero")
def _missing_not_zero(context: dict[str, object]) -> None:
    energy = _view(context)["metrics"]["energy"]
    nums = context["energy_values"]
    assert isinstance(nums, list)
    # Only the 3 logged days appear; no zero-filled entries for the 4 missing days.
    assert len(energy["values"]) == 3
    assert 0 not in [v["value"] for v in energy["values"]]
    # Average is over logged days only, never dragged toward zero by the missing ones.
    assert energy["average"] == round(sum(nums) / 3, 1)


# --- Scenario: glucose and insulin stay in my record ----------------------------------


@given("Tidepool glucose and insulin were pulled for the last 7 days")
def _glucose_insulin_pulled(seed: SeedRunner) -> None:
    async def _seed(s: AsyncSession) -> None:
        for day in WINDOW:
            await add_glucose(s, day, 8, 6.5)
            await add_glucose(s, day, 20, 7.2)
            await add_insulin(s, day, 8, 4.0, carbs=40.0)

    seed(_seed)


@then("glucose and insulin are not part of what I transfer to my PT")
def _no_glucose_insulin(context: dict[str, object]) -> None:
    view = _view(context)
    lowered = {k.lower() for k in view}
    for banned in ("glucose", "insulin", "mmol", "bolus", "carbs"):
        assert not any(banned in k for k in lowered), f"check-in exposes {banned!r}"


@then("they remain in my own record")
def _remain_in_record(bdd_client: TestClient) -> None:
    # They are readable from the diabetes record, just not in the check-in package.
    resp = bdd_client.get("/api/v1/diabetes/record", params={"days": 7, "before": START})
    assert resp.status_code == 200, resp.text
    record = resp.json()
    assert record["glucose"] is not None
    assert record["insulin_events"] > 0


# --- Scenario: completed check-in presented for transfer ------------------------------


@given("the check-in is complete")
def _fill_before_finish(bdd_client: TestClient, context: dict[str, object]) -> None:
    _start_check_in(bdd_client, context)
    cid = context["check_in_id"]
    assert (
        bdd_client.post(_M, json={"date": START, "waist_cm": 95.0, "weight_kg": 88.0}).status_code
        == 200
    )
    for day in WINDOW:
        bdd_client.put(
            f"{_DAILY}/{day}/wellbeing",
            json={"energy": 7, "motivation": 6, "stress": 4, "hunger": 3},
        )
    bdd_client.patch(f"{_CI}/{cid}", json={"worked_on": "consistency", "struggles": "none"})


@when("I finish it")
def _finish_it(bdd_client: TestClient, context: dict[str, object]) -> None:
    resp = bdd_client.post(f"{_CI}/{context['check_in_id']}/finish")
    assert resp.status_code == 200, resp.text
    assert resp.json()["completed"] is True


@then("I can view, copy or export it to fill in my PT's form")
def _view_completed(bdd_client: TestClient, context: dict[str, object]) -> None:
    # "view / copy / export" is presenting the completed, fully-assembled package.
    view: dict[str, Any] = bdd_client.get(f"{_CI}/{context['check_in_id']}").json()
    assert view["completed"] is True
    assert view["measurements"] is not None
    assert view["worked_on"] == "consistency"
    assert all(v["values"] for v in view["metrics"].values())
    # And it shows up in the list of check-ins for later reference.
    summaries = bdd_client.get(_CI).json()
    assert any(s["id"] == context["check_in_id"] and s["completed"] for s in summaries)
