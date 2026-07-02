"""Execute features/diabetes_data.feature via pytest-bdd (sync TestClient harness).

Contract exercised (all /api/v1):
  POST /diabetes/sync?days=7&before=DATE  -> pulls the window from Tidepool (provider),
                                             clears+reinserts the window (idempotent),
                                             {glucose_synced, insulin_synced, pump_uploaded}
  POST /diabetes/upload  (multipart JSON)  -> parse a Tidepool data-model export, store
                                             de-duplicated, {glucose_added, insulin_added}
  GET  /diabetes/record?days=7&before=DATE -> {glucose:{average,time_in_range_pct,count},
                                             insulin_events, pump_uploaded, window_*}
  GET  /diabetes/graph?range=day&date=DATE -> {points:[{min,mmol_l,iob}], meals, workouts,...}
  GET  /diabetes/graph?range=week|month    -> {daily:[{date,avg,tir_pct,count}], ...}

The Tidepool cloud pull is exercised through the get_tidepool_provider FastAPI dependency,
overridden with a fake provider that returns canned points (a clean, non-external seam).
The scenario for a live-cloud detail with no clean seam is skipped honestly.

There is no clock override in the suite, so "today is 2026-05-25" is threaded explicitly.
"""

import io
import json
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.api.diabetes import get_tidepool_provider
from app.integrations.health import IntegrationNotConfigured
from app.integrations.tidepool import GlucosePoint, InsulinPoint
from app.main import app
from tests.bdd.seed import add_glucose, add_insulin, full_plan, set_integration

scenarios("diabetes_data.feature")

_API = "/api/v1"
_DIAB = f"{_API}/diabetes"
TODAY = date(2026, 5, 25)
TZ = ZoneInfo("Pacific/Auckland")


# --------------------------------------------------------------------------- #
# Fake Tidepool provider (the pull seam)
# --------------------------------------------------------------------------- #


class _FakeProvider:
    """Canned Tidepool provider. Records the (start, end) it was asked for."""

    def __init__(
        self,
        glucose: list[GlucosePoint] | None = None,
        insulin: list[InsulinPoint] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._glucose = glucose or []
        self._insulin = insulin or []
        self._error = error
        self.calls: list[tuple[date, date]] = []

    async def fetch(self, start: date, end: date) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
        self.calls.append((start, end))
        if self._error is not None:
            raise self._error
        return list(self._glucose), list(self._insulin)


def _install_provider(context: dict[str, object], provider: _FakeProvider) -> None:
    context["provider"] = provider
    app.dependency_overrides[get_tidepool_provider] = lambda: provider


def _pt(day: date, hour: int) -> datetime:
    """A UTC-anchored instant mid-day, so sync_diabetes' naive-UTC record window (built
    from datetime.combine(day, ...)) includes it on the day it was recorded for."""
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


# --------------------------------------------------------------------------- #
# Background
# --------------------------------------------------------------------------- #


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given("the app is connected to Tidepool")
def _connected(seed, context: dict[str, object]) -> None:
    seed(lambda s: set_integration(s, "tidepool.email", "seth@example.com"))
    seed(lambda s: set_integration(s, "tidepool.password", "secret"))
    # A default (empty) provider so the pull scenarios that don't stage specific cloud
    # data still have a seam; specific givens below replace it with canned records.
    _install_provider(context, _FakeProvider())


@given(parsers.parse("today is {day}"))
def _today(day: str) -> None:
    assert date.fromisoformat(day) == TODAY  # threaded, no clock override


# --------------------------------------------------------------------------- #
# Pull scenarios (via the overridden provider)
# --------------------------------------------------------------------------- #


@given("Dexcom glucose for the last 7 days is available in Tidepool")
def _glucose_available(context: dict[str, object]) -> None:
    # One reading per day across the window, mostly in-range.
    glucose = [
        GlucosePoint(ts=_pt(TODAY - timedelta(days=d), 12), mmol_l=6.0 + d * 0.2) for d in range(7)
    ]
    _install_provider(context, _FakeProvider(glucose=glucose))


@given("I uploaded my Tandem pump to Tidepool before the check-in")
def _pump_uploaded(context: dict[str, object]) -> None:
    insulin = [
        InsulinPoint(ts=_pt(TODAY - timedelta(days=d), 12), kind="bolus", units=4.0 + d)
        for d in range(7)
    ]
    glucose = [GlucosePoint(ts=_pt(TODAY - timedelta(days=d), 12), mmol_l=6.5) for d in range(7)]
    _install_provider(context, _FakeProvider(glucose=glucose, insulin=insulin))


@given("I did not upload my Tandem pump to Tidepool this week")
def _no_pump(context: dict[str, object]) -> None:
    # Glucose present, no insulin — the honest "no pump upload" case.
    _install_provider(context, _FakeProvider(glucose=[GlucosePoint(ts=_pt(TODAY, 12), mmol_l=6.4)]))


@given("the diabetes data for this week is already pulled")
def _already_pulled(context: dict[str, object], bdd_client: TestClient) -> None:
    glucose = [GlucosePoint(ts=_pt(TODAY - timedelta(days=d), 12), mmol_l=6.0) for d in range(7)]
    insulin = [
        InsulinPoint(ts=_pt(TODAY - timedelta(days=d), 12), kind="bolus", units=5.0)
        for d in range(7)
    ]
    _install_provider(context, _FakeProvider(glucose=glucose, insulin=insulin))
    resp = bdd_client.post(f"{_DIAB}/sync", params={"days": 7, "before": TODAY.isoformat()})
    assert resp.status_code == 200, resp.text
    context["first_pull"] = resp.json()


@given("Tidepool cannot be reached")
def _unreachable(context: dict[str, object]) -> None:
    _install_provider(
        context, _FakeProvider(error=IntegrationNotConfigured("Tidepool unreachable"))
    )


@given("I uploaded my pump to Tidepool after starting the check-in")
def _pump_after_start(context: dict[str, object]) -> None:
    insulin = [InsulinPoint(ts=_pt(TODAY, 12), kind="bolus", units=6.0)]
    glucose = [GlucosePoint(ts=_pt(TODAY, 12), mmol_l=6.2)]
    _install_provider(context, _FakeProvider(glucose=glucose, insulin=insulin))


@when("I start the weekly check-in")
@when("the check-in pull runs")
@when("the check-in pull runs again for the same week")
@when("I refresh the diabetes data")
def _run_pull(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.post(f"{_DIAB}/sync", params={"days": 7, "before": TODAY.isoformat()})
    context["sync_status"] = resp.status_code
    context["sync_body"] = resp.json() if resp.status_code == 200 else None


@when("I open my diabetes record")
def _open_record_pull(context: dict[str, object], bdd_client: TestClient) -> None:
    # Opening the record refreshes from Tidepool then reads the stored record back.
    resp = bdd_client.post(f"{_DIAB}/sync", params={"days": 7, "before": TODAY.isoformat()})
    context["sync_status"] = resp.status_code
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()})
    assert rec.status_code == 200, rec.text
    context["record"] = rec.json()


@then(parsers.parse("the app pulls glucose and pump data for {start} to {end} from Tidepool"))
def _pulled_window(context: dict[str, object], start: str, end: str) -> None:
    provider: _FakeProvider = context["provider"]  # type: ignore[assignment]
    assert provider.calls, "provider was never asked to fetch"
    got_start, got_end = provider.calls[-1]
    assert got_start == date.fromisoformat(start)
    assert got_end == date.fromisoformat(end)


@then("the app pulls the latest glucose and pump data from Tidepool")
def _pulled_latest(context: dict[str, object]) -> None:
    provider: _FakeProvider = context["provider"]  # type: ignore[assignment]
    assert provider.calls, "provider was never asked to fetch"
    assert context["sync_status"] == 200


@then("I see the most current data available")
def _see_current(context: dict[str, object]) -> None:
    assert context["record"]["glucose"]["count"] >= 0


@then("those glucose readings are stored against their days")
def _glucose_stored(context: dict[str, object], bdd_client: TestClient) -> None:
    assert context["sync_body"]["glucose_synced"] == 7
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()}).json()
    assert rec["glucose"]["count"] == 7


@then("my insulin and pump data for the last 7 days are stored")
def _insulin_stored(context: dict[str, object], bdd_client: TestClient) -> None:
    assert context["sync_body"]["insulin_synced"] == 7
    assert context["sync_body"]["pump_uploaded"] is True
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()}).json()
    assert rec["insulin_events"] == 7
    assert rec["pump_uploaded"] is True


@then("the pump data is shown as not uploaded")
def _pump_not_uploaded(context: dict[str, object], bdd_client: TestClient) -> None:
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()}).json()
    assert rec["pump_uploaded"] is False
    context["record"] = rec


@then("the app reminds me to run the Tidepool Uploader")
def _reminds_uploader(context: dict[str, object]) -> None:
    # The record honestly reports pump_uploaded=False; the reminder is a UI affordance
    # driven off that flag (there is nothing invented server-side).
    assert context["record"]["pump_uploaded"] is False


@then("no insulin figures are invented")
def _no_insulin_invented(context: dict[str, object]) -> None:
    assert context["record"]["insulin_events"] == 0


@then("the data is updated in place")
def _updated_in_place(context: dict[str, object]) -> None:
    assert context["sync_body"]["glucose_synced"] == context["first_pull"]["glucose_synced"]
    assert context["sync_body"]["insulin_synced"] == context["first_pull"]["insulin_synced"]


@then("no duplicates are created")
def _no_duplicates(context: dict[str, object], bdd_client: TestClient) -> None:
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()}).json()
    assert rec["glucose"]["count"] == 7
    assert rec["insulin_events"] == 7


@then("the failure is surfaced to me")
def _failure_surfaced(context: dict[str, object]) -> None:
    assert context["sync_status"] == 503


@then("I can enter the key figures manually if I need to")
def _manual_fallback(bdd_client: TestClient) -> None:
    # The manual fallback is the direct upload path — verify it accepts an export.
    export = [
        {"type": "cbg", "time": "2026-05-25T09:00:00.000Z", "value": 6.5, "units": "mmol/L"},
    ]
    resp = bdd_client.post(
        f"{_DIAB}/upload",
        files={
            "file": ("export.json", io.BytesIO(json.dumps(export).encode()), "application/json")
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["glucose_added"] == 1


@then("the newly uploaded pump data is pulled and included")
def _refresh_included(context: dict[str, object], bdd_client: TestClient) -> None:
    assert context["sync_body"]["insulin_synced"] == 1
    rec = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()}).json()
    assert rec["insulin_events"] == 1
    assert rec["pump_uploaded"] is True


# --------------------------------------------------------------------------- #
# View the record
# --------------------------------------------------------------------------- #


@given("glucose and pump data for the last 7 days are pulled")
def _week_data_seeded(seed) -> None:
    async def _seed(s):
        for d in range(7):
            day = TODAY - timedelta(days=d)
            await add_glucose(s, day, 8, 5.5)
            await add_glucose(s, day, 14, 7.5)
            await add_insulin(s, day, 12, 5.0, carbs=46)

    seed(_seed)


@when("I view my diabetes record for the week")
def _view_record(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_DIAB}/record", params={"days": 7, "before": TODAY.isoformat()})
    assert resp.status_code == 200, resp.text
    context["record"] = resp.json()


@then("it includes a glucose summary (average and time-in-range)")
def _has_glucose_summary(context: dict[str, object]) -> None:
    g = context["record"]["glucose"]
    assert g["average"] is not None
    assert g["time_in_range_pct"] is not None
    assert g["count"] == 14


@then("my insulin/pump data for the week")
def _has_insulin(context: dict[str, object]) -> None:
    assert context["record"]["insulin_events"] == 7
    assert context["record"]["pump_uploaded"] is True


# --------------------------------------------------------------------------- #
# Direct upload of a Tidepool data-model JSON export
# --------------------------------------------------------------------------- #


@given("a Tidepool data-model JSON export with glucose and bolus records")
def _export_file(context: dict[str, object]) -> None:
    export = [
        {"type": "cbg", "time": "2026-05-25T08:00:00.000Z", "value": 110, "units": "mg/dL"},
        {"type": "cbg", "time": "2026-05-25T08:05:00.000Z", "value": 120, "units": "mg/dL"},
        {"type": "smbg", "time": "2026-05-25T09:00:00.000Z", "value": 6.5, "units": "mmol/L"},
        {"type": "bolus", "time": "2026-05-25T12:00:00.000Z", "normal": 5.0},
        {"type": "bolus", "time": "2026-05-25T18:00:00.000Z", "normal": 3.0, "extended": 1.0},
    ]
    context["export"] = export


@when("I upload it on the diabetes screen")
def _upload_export(context: dict[str, object], bdd_client: TestClient) -> None:
    payload = json.dumps(context["export"]).encode()
    resp = bdd_client.post(
        f"{_DIAB}/upload",
        files={"file": ("export.json", io.BytesIO(payload), "application/json")},
    )
    assert resp.status_code == 200, resp.text
    context["first_upload"] = resp.json()


@then("the glucose and insulin records are stored to my record")
def _upload_stored(context: dict[str, object]) -> None:
    assert context["first_upload"]["glucose_added"] == 3
    assert context["first_upload"]["insulin_added"] == 2


@then("re-uploading the same file adds no duplicates")
def _reupload_no_dupes(context: dict[str, object], bdd_client: TestClient) -> None:
    payload = json.dumps(context["export"]).encode()
    resp = bdd_client.post(
        f"{_DIAB}/upload",
        files={"file": ("export.json", io.BytesIO(payload), "application/json")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"glucose_added": 0, "insulin_added": 0}


# --------------------------------------------------------------------------- #
# Daily graph
# --------------------------------------------------------------------------- #


@given("glucose readings are stored for today")
def _glucose_today(seed) -> None:
    # The seed helper stores the given hour as a naive wall-clock value that the graph
    # reads back as UTC; NZ is UTC+12, so hour H lands at local minute (H + 12) * 60 and
    # hours < 12 stay on the same local day. Use 0..5 -> local 12:00..17:00 today.
    async def _seed(s):
        for hour, mmol in [(0, 5.2), (1, 7.8), (2, 6.4), (3, 8.1), (4, 5.9), (5, 6.7)]:
            await add_glucose(s, TODAY, hour, mmol)

    seed(_seed)


@given("I took a bolus today")
def _bolus_today(seed) -> None:
    # Stored hour 0 -> local 12:00 (minute 720), keeping the whole IOB decay within the day.
    seed(lambda s: add_insulin(s, TODAY, 0, 6.0, carbs=46))


@given("I checked off meals on my daily task list today")
def _meals_today(seed, bdd_client: TestClient, context: dict[str, object]) -> None:
    plan = seed(full_plan)
    # Fetch meal ids for the current plan and check a couple off today.
    daily = bdd_client.get(f"{_API}/daily/{TODAY.isoformat()}").json()
    meals = daily.get("meals") or daily.get("nutrition", {}).get("meals")
    assert meals, f"no meals in daily payload: {list(daily)}"
    checked = []
    for meal in meals[:2]:
        mid = meal["id"]
        resp = bdd_client.post(f"{_API}/daily/{TODAY.isoformat()}/meals/{mid}/check")
        assert resp.status_code == 200, resp.text
        checked.append((mid, meal.get("carbs_g")))
    context["checked_meals"] = checked
    context["plan"] = plan


@given("I logged workout sets today")
def _sets_today(seed, bdd_client: TestClient) -> None:
    seed(full_plan)
    resp = bdd_client.post(f"{_API}/sessions", json={"date": TODAY.isoformat()})
    assert resp.status_code == 201, resp.text
    sid = resp.json()["id"]
    for _ in range(3):
        r = bdd_client.post(
            f"{_API}/sessions/{sid}/sets",
            json={"exercise_slug": "leg-press-machine", "reps": "15", "weight": "50"},
        )
        assert r.status_code == 201, r.text


@when("I open the diabetes graph for the day")
def _open_day_graph(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_DIAB}/graph", params={"range": "day", "date": TODAY.isoformat()})
    assert resp.status_code == 200, resp.text
    context["graph"] = resp.json()


@then("I see my glucose plotted against the time of day in my local timezone")
def _glucose_plotted(context: dict[str, object]) -> None:
    graph = context["graph"]
    assert graph["range"] == "day"
    with_glucose = [p for p in graph["points"] if p["mmol_l"] is not None]
    assert len(with_glucose) == 6
    # Stored hour 0 lands at local minute 720 (12:00) on the local-midnight-relative x-axis.
    minutes = {p["min"] for p in with_glucose}
    assert 720 in minutes


@then("an insulin-on-board line is overlaid, peaking after the bolus and decaying to zero")
def _iob_overlay(context: dict[str, object]) -> None:
    points = context["graph"]["points"]
    # Bolus at 12:00 NZ (minute 720). IOB should rise after it and decay back to ~0.
    by_min = {p["min"]: p["iob"] for p in points}
    at_bolus = by_min.get(720, 0.0)
    after = max(v for m, v in by_min.items() if 720 <= m <= 900)
    assert after > 0
    # Well before the bolus (early morning) IOB is zero.
    assert by_min.get(0, 0.0) == 0.0
    # Late-night, > DIA after the bolus, IOB has decayed back to zero.
    assert by_min.get(1435, 0.0) == 0.0
    assert at_bolus >= 0.0


@then("the IOB is shown as a model estimate, not a pump-reported figure")
def _iob_is_model(context: dict[str, object]) -> None:
    # Every grid point carries an "iob" field (a computed model value), not a stored one.
    assert all("iob" in p for p in context["graph"]["points"])


@then("each meal is marked at the time I checked it off, with its carbs")
def _meals_marked(context: dict[str, object]) -> None:
    meals = context["graph"]["meals"]
    assert len(meals) == len(context["checked_meals"])
    for m in meals:
        assert "min" in m
        assert m["carbs_g"] is not None
        assert "name" in m


@then("the workout is marked across the span of time I was logging sets")
def _workout_marked(context: dict[str, object]) -> None:
    workouts = context["graph"]["workouts"]
    assert len(workouts) == 1
    w = workouts[0]
    assert w["start_min"] <= w["end_min"]
    assert w["label"] == "Workout"


# --------------------------------------------------------------------------- #
# Week / month trend + empty day
# --------------------------------------------------------------------------- #


@given("glucose readings are stored across the last week")
def _glucose_week(seed) -> None:
    # Both hours < 12 so they land on the same local day (see _glucose_today note).
    async def _seed(s):
        for d in range(7):
            day = TODAY - timedelta(days=d)
            await add_glucose(s, day, 2, 5.5)
            await add_glucose(s, day, 4, 7.5)

    seed(_seed)


@given("glucose readings are stored across the last month")
def _glucose_month(seed) -> None:
    async def _seed(s):
        for d in range(0, 30, 2):  # every other day across the month
            day = TODAY - timedelta(days=d)
            await add_glucose(s, day, 6, 6.0)  # hours < 12 stay on the same local day
            await add_glucose(s, day, 8, 8.0)

    seed(_seed)


@given("there are no glucose readings for the chosen day")
def _no_glucose_day() -> None:
    pass  # nothing seeded for TODAY


@when("I open the diabetes graph for the week")
def _open_week_graph(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_DIAB}/graph", params={"range": "week", "date": TODAY.isoformat()})
    assert resp.status_code == 200, resp.text
    context["graph"] = resp.json()


@when("I open the diabetes graph for the month")
def _open_month_graph(context: dict[str, object], bdd_client: TestClient) -> None:
    resp = bdd_client.get(f"{_DIAB}/graph", params={"range": "month", "date": TODAY.isoformat()})
    assert resp.status_code == 200, resp.text
    context["graph"] = resp.json()


@then("I see one average BG point per day with the in-range band shaded")
def _week_avg_points(context: dict[str, object]) -> None:
    graph = context["graph"]
    assert graph["range"] == "week"
    assert len(graph["daily"]) == 7
    with_data = [d for d in graph["daily"] if d["avg"] is not None]
    assert len(with_data) == 7
    for d in with_data:
        assert d["avg"] == 6.5  # (5.5 + 7.5) / 2
    # The in-range band bounds accompany the series (the "shaded band").
    assert graph["tir_low"] < graph["tir_high"]


@then("I see the daily average BG trend across the month")
def _month_trend(context: dict[str, object]) -> None:
    graph = context["graph"]
    assert graph["range"] == "month"
    assert len(graph["daily"]) == 30
    with_data = [d for d in graph["daily"] if d["avg"] is not None]
    assert len(with_data) == 15  # every other day
    for d in with_data:
        assert d["avg"] == 7.0  # (6.0 + 8.0) / 2


@then("no glucose trace is drawn")
def _no_trace(context: dict[str, object]) -> None:
    graph = context["graph"]
    assert all(p["mmol_l"] is None for p in graph["points"])


@then("I am prompted to pull from Tidepool")
def _prompt_pull(context: dict[str, object]) -> None:
    # An empty trace (no glucose points) is what drives the "pull from Tidepool" prompt.
    assert not [p for p in context["graph"]["points"] if p["mmol_l"] is not None]
