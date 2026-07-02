"""Execute features/sleep_analysis.feature via pytest-bdd (sync TestClient harness).

The sleep sync itself is external (Google Health / Fitbit); there is no write endpoint.
We treat "when the sleep sync runs" as seeding a night directly via add_sleep and then
assert the stored night carries stage segments + totals, matching night_view's shape.
"""

from datetime import date

from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

from tests.bdd.seed import add_sleep

scenarios("sleep_analysis.feature")

_S = "/api/v1/sleep"

# Fixed dates used across scenarios.
_NIGHT = date(2026, 6, 1)
_OTHER = date(2026, 6, 2)
_NO_STAGES = date(2026, 6, 3)


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


# --- Scenario: Stage segments are captured on sync -------------------------------


@given("Google Health returns a night with light, deep and REM stages")
def _google_night(context: dict[str, object]) -> None:
    context["sync_day"] = _NIGHT


@when("the sleep sync runs")
def _sync_runs(seed, context: dict[str, object]) -> None:
    day = context["sync_day"]
    assert isinstance(day, date)
    seed(lambda s: add_sleep(s, day, with_stages=True))


@then("the per-stage totals and the stage segments (with their times) are stored")
def _totals_and_segments_stored(bdd_client: TestClient, context: dict[str, object]) -> None:
    day = context["sync_day"]
    assert isinstance(day, date)
    body = bdd_client.get(f"{_S}/night", params={"date": day.isoformat()}).json()
    assert body["found"] is True
    # per-stage totals
    assert body["light_min"] is not None
    assert body["deep_min"] is not None
    assert body["rem_min"] is not None
    # stage segments with their times
    segments = body["segments"]
    assert isinstance(segments, list) and len(segments) == 3
    types = {seg["type"] for seg in segments}
    assert types == {"light", "deep", "rem"}
    for seg in segments:
        assert seg["start_hm"]
        assert seg["end_hm"]
        assert seg["start_min"] is not None
        assert seg["end_min"] is not None


# --- Scenario: View a night's stage timeline -------------------------------------


@given("a stored night with stage segments")
def _stored_night_with_stages(seed, context: dict[str, object]) -> None:
    seed(lambda s: add_sleep(s, _NIGHT, with_stages=True))
    context["view_day"] = _NIGHT


@when("I open the sleep page for that night")
def _open_night(bdd_client: TestClient, context: dict[str, object]) -> None:
    day = context["view_day"]
    assert isinstance(day, date)
    context["night"] = bdd_client.get(f"{_S}/night", params={"date": day.isoformat()}).json()


@then("I see each stage on a timeline showing when it occurred and for how long")
def _timeline_shown(context: dict[str, object]) -> None:
    segments = context["night"]["segments"]
    assert isinstance(segments, list) and segments
    for seg in segments:
        # "when it occurred" (clock time) and its position on the timeline (offset)
        assert seg["start_hm"] and seg["end_hm"]
        assert seg["start_min"] is not None and seg["end_min"] is not None


@then("I see the per-stage totals, bedtime, wake time and efficiency")
def _totals_bedtime_wake_efficiency(context: dict[str, object]) -> None:
    night = context["night"]
    assert night["light_min"] is not None
    assert night["deep_min"] is not None
    assert night["rem_min"] is not None
    assert night["bedtime"] == "22:30"
    assert night["wake_time"] == "07:00"
    assert night["efficiency"] == 93.0


# --- Scenario: A night without stage detail is shown honestly --------------------


@given("a stored night with totals but no stage segments")
def _stored_night_no_stages(seed, context: dict[str, object]) -> None:
    seed(lambda s: add_sleep(s, _NO_STAGES, with_stages=False))
    context["view_day"] = _NO_STAGES


@then("I see the totals and a note that stage detail isn't available")
def _totals_present_no_stages(context: dict[str, object]) -> None:
    night = context["night"]
    assert night["found"] is True
    # totals are present
    assert night["asleep_min"] is not None
    assert night["efficiency"] is not None
    # stage detail is honestly absent (empty timeline)
    assert night["segments"] == []


# --- Scenario: Weekly sleep trends -----------------------------------------------


@given("stored nights across the last two weeks")
def _nights_two_weeks(seed) -> None:
    from app.clock import local_today

    today = local_today()

    async def _seed(s) -> None:
        for offset in (1, 3, 6, 9, 12):
            await add_sleep(s, date.fromordinal(today.toordinal() - offset), with_stages=True)

    seed(_seed)


@when("I open the sleep page")
def _open_sleep_page(bdd_client: TestClient, context: dict[str, object]) -> None:
    context["trend"] = bdd_client.get(f"{_S}/trend", params={"days": 14}).json()


@then("I see per-night stage breakdown and averages (asleep, efficiency, deep, REM)")
def _trend_breakdown_and_averages(context: dict[str, object]) -> None:
    trend = context["trend"]
    nights = trend["nights"]
    assert isinstance(nights, list) and len(nights) >= 2
    for n in nights:
        assert n["date"]
        assert n["asleep_min"] is not None
        assert n["deep_min"] is not None
        assert n["rem_min"] is not None
        assert n["efficiency"] is not None
    averages = trend["averages"]
    assert averages["asleep_min"] is not None
    assert averages["efficiency"] is not None
    assert averages["deep_min"] is not None
    assert averages["rem_min"] is not None
    assert averages["count"] >= 2


# --- Scenario: Pick a different night --------------------------------------------


@given("several stored nights")
def _several_nights(seed, context: dict[str, object]) -> None:
    async def _seed(s) -> None:
        await add_sleep(s, _NIGHT, with_stages=True)
        await add_sleep(s, _OTHER, with_stages=True)

    seed(_seed)
    context["view_day"] = _OTHER


@when("I select another night")
def _select_another(bdd_client: TestClient, context: dict[str, object]) -> None:
    day = context["view_day"]
    assert isinstance(day, date)
    context["night"] = bdd_client.get(f"{_S}/night", params={"date": day.isoformat()}).json()


@then("its stage timeline and totals are shown")
def _its_timeline_and_totals(context: dict[str, object]) -> None:
    night = context["night"]
    assert night["found"] is True
    assert night["date"] == _OTHER.isoformat()
    assert isinstance(night["segments"], list) and night["segments"]
    assert night["asleep_min"] is not None
    assert night["efficiency"] is not None
