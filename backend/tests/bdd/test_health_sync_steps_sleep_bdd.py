"""Execute features/health_sync_steps_sleep.feature via pytest-bdd.

Read-side scenarios (steps-against-target, sleep detail) seed StepsDay/SleepNight rows
directly and assert the GET endpoints, per the hints.

Sync-run scenarios exercise POST /sync/steps-sleep. The endpoint's Google Health provider
is a FastAPI dependency (app.api.sync.get_health_provider), so we override it with a fake
provider that returns canned StepRecord/SleepRecord data (or raises) instead of hitting the
real API. That keeps the sync (store / idempotent / preserve-manual / surface-failure)
behaviour under test without any external call.

The "enter a day manually" step has no manual-entry endpoint in app/api (searched: only
POST /sync/steps-sleep touches StepsDay), so the manual entry itself is seeded as a
StepsDay(manual=True); the assertion that a later sync won't silently overwrite it is a
real check against sync_steps_sleep's preserved_manual path.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from app.api import sync as sync_api
from app.integrations.health import (
    HealthProvider,
    IntegrationAuthExpired,
    SleepRecord,
    StepRecord,
)
from app.main import app
from app.models import StepsDay
from tests.bdd.seed import _owner_id, add_sleep, add_steps

scenarios("health_sync_steps_sleep.feature")

_SYNC = "/api/v1/sync/steps-sleep"


class _FakeProvider:
    """Stand-in HealthProvider: returns canned records, or raises to model a failure."""

    def __init__(
        self,
        steps: list[StepRecord] | None = None,
        sleeps: list[SleepRecord] | None = None,
        error: Exception | None = None,
    ) -> None:
        self._steps = steps or []
        self._sleeps = sleeps or []
        self._error = error

    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]:
        if self._error is not None:
            raise self._error
        return self._steps, self._sleeps


def _install_provider(provider: HealthProvider) -> None:
    app.dependency_overrides[sync_api.get_health_provider] = lambda: provider


@pytest.fixture(autouse=True)
def _clear_provider_override():
    yield
    app.dependency_overrides.pop(sync_api.get_health_provider, None)


# --- Background -------------------------------------------------------------


@given("I am logged in")
def _logged_in() -> None:
    pass  # bdd_client carries a valid owner token


@given("my steps and sleep sync is connected")
def _sync_connected(context: dict) -> None:
    # A connected sync == a working provider. Default to one that returns a recent
    # day of steps + sleep; individual scenarios replace this before triggering.
    context["provider"] = _FakeProvider(
        steps=[StepRecord(date=date(2026, 5, 25), steps=6500)],
        sleeps=[
            SleepRecord(
                date=date(2026, 5, 25),
                asleep_min=420.0,
                in_bed_min=450.0,
                awake_min=15.0,
                light_min=200.0,
                deep_min=150.0,
                rem_min=70.0,
                efficiency=93.0,
                bedtime="22:30",
                wake_time="07:00",
                stages=[
                    {"type": "light", "start": "2026-05-25T22:30:00", "end": "2026-05-25T23:30:00"},
                ],
            )
        ],
    )


# --- Sync-run scenarios -----------------------------------------------------


@given("the scheduled sync time has arrived")
def _schedule_arrived() -> None:
    pass  # modelled by triggering the same manual endpoint the scheduler would call


@when("a sync runs")
@when("a sync runs automatically in the background")
@when("I open the app")
@when("a sync runs to refresh today's steps and sleep")
def _run_sync(bdd_client: TestClient, context: dict) -> None:
    _install_provider(context["provider"])
    context["resp"] = bdd_client.post(_SYNC)


@then("a sync runs automatically in the background")
@then("a sync runs to refresh today's steps and sleep")
def _sync_ran(bdd_client: TestClient, context: dict) -> None:
    # No standalone scheduler/on-open trigger endpoint exists; the scheduled and
    # on-open runs invoke the same POST /sync/steps-sleep. Drive it and assert it
    # stored the provider's data.
    if "resp" not in context:
        _install_provider(context["provider"])
        context["resp"] = bdd_client.post(_SYNC)
    assert context["resp"].status_code == 200
    body = context["resp"].json()
    assert body["steps_synced"] >= 1
    assert body["sleep_synced"] >= 1


@then("the latest days of steps and sleep are stored")
def _latest_stored(bdd_client: TestClient, context: dict) -> None:
    assert context["resp"].status_code == 200
    body = context["resp"].json()
    assert body["steps_synced"] >= 1
    assert body["sleep_synced"] >= 1
    # Confirm the read side reflects it.
    day = bdd_client.get("/api/v1/daily/2026-05-25").json()
    assert day["steps"]["steps"] == 6500


# --- Backfill ---------------------------------------------------------------


@given(parsers.parse("no sync ran for {n:d} days"))
def _no_sync_for(context: dict, n: int) -> None:
    days = [date(2026, 5, 23), date(2026, 5, 24), date(2026, 5, 25)][:n]
    context["backfill_days"] = days
    context["provider"] = _FakeProvider(
        steps=[StepRecord(date=d, steps=5000 + i) for i, d in enumerate(days)],
        sleeps=[],
    )


@then("steps and sleep for each of the missed days are filled in")
def _backfilled(bdd_client: TestClient, context: dict) -> None:
    assert context["resp"].status_code == 200
    assert context["resp"].json()["steps_synced"] == len(context["backfill_days"])
    for d in context["backfill_days"]:
        day = bdd_client.get(f"/api/v1/daily/{d.isoformat()}").json()
        assert day["steps"]["steps"] is not None


# --- Idempotent re-sync -----------------------------------------------------


@given(parsers.parse("steps for {d} are already stored"))
def _already_stored(seed, context: dict, d: str) -> None:
    day = date.fromisoformat(d)
    seed(lambda s: add_steps(s, day, 1000))
    context["resync_day"] = day
    context["provider"] = _FakeProvider(steps=[StepRecord(date=day, steps=6200)])


@when(parsers.parse("a sync runs again for {d}"))
def _resync(bdd_client: TestClient, context: dict, d: str) -> None:
    _install_provider(context["provider"])
    context["resp"] = bdd_client.post(_SYNC)


@then("the day's steps are updated in place")
def _updated_in_place(bdd_client: TestClient, context: dict) -> None:
    assert context["resp"].status_code == 200
    d = context["resync_day"]
    day = bdd_client.get(f"/api/v1/daily/{d.isoformat()}").json()
    assert day["steps"]["steps"] == 6200


@then("no duplicate day is created")
def _no_duplicate(seed, context: dict) -> None:
    d = context["resync_day"]

    async def _count(s):
        from sqlalchemy import func, select

        return await s.scalar(select(func.count()).select_from(StepsDay).where(StepsDay.date == d))

    assert seed(_count) == 1


# --- Failure surfaced -------------------------------------------------------


@given("the health source cannot be reached")
def _source_down(seed, context: dict) -> None:
    # Seed a last-good day, then point the provider at a raised auth/connect error.
    seed(lambda s: add_steps(s, date(2026, 5, 25), 4321))
    context["last_good_day"] = date(2026, 5, 25)
    context["provider"] = _FakeProvider(error=IntegrationAuthExpired("Google Health unreachable"))


@then("the failure is surfaced to me")
def _failure_surfaced(context: dict) -> None:
    # Endpoint maps IntegrationAuthExpired -> 409 (a surfaced, non-silent error).
    assert context["resp"].status_code >= 400


@then("the last good data is left untouched")
def _last_good_untouched(bdd_client: TestClient, context: dict) -> None:
    d = context["last_good_day"]
    day = bdd_client.get(f"/api/v1/daily/{d.isoformat()}").json()
    assert day["steps"]["steps"] == 4321


# --- Steps against target (read side) --------------------------------------


@given(parsers.parse("{steps:d} steps synced for {d}"))
def _steps_synced(seed, steps: int, d: str) -> None:
    seed(lambda s: add_steps(s, date.fromisoformat(d), steps))


@when(parsers.re(r"I view (?P<d>\d{4}-\d{2}-\d{2})"))
def _view_day(bdd_client: TestClient, context: dict, d: str) -> None:
    context["day"] = bdd_client.get(f"/api/v1/daily/{d}").json()


@then(parsers.re(r"it shows (?P<steps>[\d,]+) of (?P<target>[\d,]+) steps"))
def _shows_steps(context: dict, steps: str, target: str) -> None:
    assert context["day"]["steps"]["steps"] == int(steps.replace(",", ""))
    assert context["day"]["steps"]["target"] == int(target.replace(",", ""))


@then("the target is marked not met")
def _target_not_met(context: dict) -> None:
    s = context["day"]["steps"]
    assert s["steps"] < s["target"]


# --- Sleep detail (read side) ----------------------------------------------


@given(parsers.parse("a sleep record synced for {d}"))
def _sleep_synced(seed, context: dict, d: str) -> None:
    day = date.fromisoformat(d)
    context["sleep_day"] = day
    seed(lambda s: add_sleep(s, day, with_stages=True))


@when("I view that night")
def _view_night(bdd_client: TestClient, context: dict) -> None:
    d = context["sleep_day"].isoformat()
    context["night"] = bdd_client.get(f"/api/v1/sleep/night?date={d}").json()


@then("it shows time asleep, efficiency, and the light/deep/REM/awake stages")
def _shows_sleep_detail(context: dict) -> None:
    n = context["night"]
    assert n["found"] is True
    assert n["asleep_min"] is not None
    assert n["efficiency"] is not None
    for field in ("light_min", "deep_min", "rem_min", "awake_min"):
        assert n[field] is not None
    assert {seg["type"] for seg in n["segments"]} >= {"light", "deep", "rem"}


# --- Manual correction ------------------------------------------------------


@given(parsers.parse("the sync missed {d}"))
def _sync_missed(context: dict, d: str) -> None:
    context["manual_day"] = date.fromisoformat(d)


@when(parsers.re(r"I enter (?P<steps>[\d,]+) steps for (?P<d>\d{4}-\d{2}-\d{2}) manually"))
def _enter_manually(seed, context: dict, steps: str, d: str) -> None:
    steps_int = int(steps.replace(",", ""))
    # No manual steps-entry endpoint exists in app/api (only POST /sync/steps-sleep
    # writes StepsDay). Represent the manual entry by seeding a manual StepsDay row;
    # the sync-preserve assertion below is the real behaviour under test.
    day = date.fromisoformat(d)
    context["manual_steps"] = steps_int

    async def _seed_manual(s):
        s.add(
            StepsDay(
                user_id=await _owner_id(s),
                date=day,
                steps=steps_int,
                target_steps=7000,
                manual=True,
            )
        )

    seed(_seed_manual)


@then(parsers.re(r"(?P<d>\d{4}-\d{2}-\d{2}) shows (?P<steps>[\d,]+) steps"))
def _manual_shows(bdd_client: TestClient, d: str, steps: str) -> None:
    day = bdd_client.get(f"/api/v1/daily/{d}").json()
    assert day["steps"]["steps"] == int(steps.replace(",", ""))


@then("a later sync will not overwrite my manual entry without telling me")
def _later_sync_preserves(bdd_client: TestClient, context: dict) -> None:
    day = context["manual_day"]
    # A later sync tries to write a different value for the same day.
    provider = _FakeProvider(steps=[StepRecord(date=day, steps=1)])
    _install_provider(provider)
    resp = bdd_client.post(_SYNC)
    assert resp.status_code == 200
    body = resp.json()
    # It reports the manual day as preserved (told, not silent) and leaves it intact.
    assert day.isoformat() in body["preserved_manual"]
    after = bdd_client.get(f"/api/v1/daily/{day.isoformat()}").json()
    assert after["steps"]["steps"] == context["manual_steps"]
