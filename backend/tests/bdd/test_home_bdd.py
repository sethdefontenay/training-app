"""Execute features/home.feature via pytest-bdd.

Home is a client-side hub (a launcher screen), so the "landing"/"prominence" steps are
UI-only no-ops. The substantive assertion is that every area the hub links to is actually
reachable on the backend — each area's endpoint responds for the owner.
"""

from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from tests.bdd.seed import full_plan

scenarios("home.feature")

_TODAY = "2026-05-25"  # a Monday — full_plan maps it to Training Day 1


@given("I am logged in")
def _login(seed) -> None:
    seed(full_plan)  # so the linked areas have real data to return


@given("I am on the Home hub")
@then("I am on the Home hub")
def _home_hub() -> None:
    pass  # UI-only: Home is a client-side launcher screen


@when("I open the app and log in")
def _open_and_login() -> None:
    pass  # UI-only: landing on Home after login is client-side routing


@when(parsers.parse('I open "{area}"'))
def _open_area(area: str, context: dict) -> None:
    context["area"] = area


@then("I am on today's daily task list")
def _on_daily(bdd_client: TestClient) -> None:
    assert bdd_client.get(f"/api/v1/daily/{_TODAY}").status_code == 200


def _reachable(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200, path


@then("I can reach the weekly shopping list")
def _shopping(bdd_client: TestClient) -> None:
    bdd_client.post("/api/v1/shopping/regenerate")
    _reachable(bdd_client, "/api/v1/shopping")


@then("I can reach the weekly check-in")
def _checkin(bdd_client: TestClient) -> None:
    _reachable(bdd_client, "/api/v1/check-ins")


@then("I can reach my measurements")
def _measurements(bdd_client: TestClient) -> None:
    _reachable(bdd_client, "/api/v1/measurements")


@then("I can reach my exercise history")
def _history(bdd_client: TestClient) -> None:
    _reachable(bdd_client, "/api/v1/sessions")


@then("I can reach my current plan")
def _plan(bdd_client: TestClient) -> None:
    _reachable(bdd_client, "/api/v1/plans/current/detail")


@then("I can reach settings")
def _settings(bdd_client: TestClient) -> None:
    _reachable(bdd_client, "/api/v1/settings/google-health")


@then("I see a quick status for today")
def _quick_status(bdd_client: TestClient) -> None:
    # The hub's "today at a glance" is drawn from the daily view.
    assert bdd_client.get(f"/api/v1/daily/{_TODAY}").status_code == 200


@then("today's tasks are the most prominent thing")
def _prominent() -> None:
    pass  # UI-only: visual prominence is a layout concern
