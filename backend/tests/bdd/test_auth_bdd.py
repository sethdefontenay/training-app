"""Execute features/auth.feature via pytest-bdd (sync TestClient harness).

Login/session is a JWT held client-side; the backend is stateless. Steps assert the
backend truths the client relies on: correct creds mint a token that reaches protected
data, wrong creds / no token / garbage token / expired token all yield 401. Scenarios
about the session "persisting on the phone", "logging out" and "reopening the app" are
client-side (the browser holds/drops the JWT) — those steps assert the backend truth
(a freshly issued token still authorizes; there is no server session to invalidate) and
are marked ``# UI-only:``.
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt
from pytest_bdd import given, scenarios, then, when

from app.main import app
from app.security import settings

scenarios("auth.feature")

_LOGIN = "/api/v1/auth/login"
_PROTECTED = "/api/v1/daily/2026-05-25"

_OWNER = {"email": "seth@example.com", "password": "pw"}


def _bare_client() -> TestClient:
    """A TestClient with no default Authorization header (unlike bdd_client)."""
    return TestClient(app)


@given("the app has a single account with my email and password")
def _account_exists(bdd_env: dict) -> None:
    pass  # bdd_env seeds the owner (seth@example.com / pw) before every scenario


# --- Scenario: Logging in with the right credentials grants access ---


@when("I log in with my correct email and password")
def _login_correct(bdd_env: dict, context: dict) -> None:
    resp = _bare_client().post(_LOGIN, json=_OWNER)
    context["login"] = resp


@then("I reach the app")
def _reach_app(context: dict) -> None:
    resp = context["login"]
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    # The freshly minted token must actually authorize protected data.
    client = _bare_client()
    protected = client.get(_PROTECTED, headers={"Authorization": f"Bearer {token}"})
    assert protected.status_code == 200


# --- Scenario: A wrong password is rejected ---


@when("I log in with my email and the wrong password")
def _login_wrong(bdd_env: dict, context: dict) -> None:
    resp = _bare_client().post(_LOGIN, json={"email": _OWNER["email"], "password": "nope"})
    context["login"] = resp


@then("I am not let in")
def _not_let_in(context: dict) -> None:
    assert context["login"].status_code == 401


@then("no data is shown")
def _no_data(context: dict) -> None:
    # A 401 response body carries no user data, only an error detail.
    assert "access_token" not in context["login"].json()


# --- Scenario: Protected data requires login ---


@given("I am not logged in")
def _not_logged_in(bdd_env: dict, context: dict) -> None:
    context["client"] = _bare_client()


@when("I try to open today's list")
def _open_list(context: dict) -> None:
    context["resp"] = context["client"].get(_PROTECTED, headers={"Authorization": ""})


@then("I am asked to log in first")
def _asked_to_login(context: dict) -> None:
    assert context["resp"].status_code == 401


# --- Scenario: My session persists on my device (UI-only) ---


@given("I logged in on my phone")
def _logged_in_phone(bdd_env: dict, context: dict) -> None:
    # UI-only: the phone stores the JWT in the browser. Backend truth we can assert is
    # that logging in mints a token; capture it for the "reopen" step.
    resp = _bare_client().post(_LOGIN, json=_OWNER)
    assert resp.status_code == 200
    context["token"] = resp.json()["access_token"]


@when("I reopen the app later that day")
def _reopen_app(context: dict) -> None:
    # UI-only: reopening replays the stored JWT; the backend just validates it again.
    client = _bare_client()
    context["resp"] = client.get(
        _PROTECTED, headers={"Authorization": f"Bearer {context['token']}"}
    )


@then("I am still logged in")
def _still_logged_in(context: dict) -> None:
    # Backend truth: the same unexpired token still authorizes — no server session needed.
    assert context["resp"].status_code == 200


# --- Scenario: Logging out ends the session (UI-only) ---


@given("I am logged in")
def _am_logged_in(bdd_env: dict, context: dict) -> None:
    resp = _bare_client().post(_LOGIN, json=_OWNER)
    assert resp.status_code == 200
    context["token"] = resp.json()["access_token"]


@when("I log out")
def _log_out(context: dict) -> None:
    # UI-only: logout is purely client-side — the browser discards its JWT. There is no
    # server session to invalidate, so we model the logged-out client as one with no token.
    context["token"] = None


@then("I must log in again to get back in")
def _must_login_again(context: dict) -> None:
    # Backend truth: with the token discarded, protected data is refused (401).
    client = _bare_client()
    resp = client.get(_PROTECTED, headers={"Authorization": ""})
    assert resp.status_code == 401


# --- Scenario: An expired session requires re-authentication ---


@given("my session has expired")
def _session_expired(bdd_env: dict, context: dict) -> None:
    expired = datetime.now(UTC) - timedelta(minutes=1)
    context["token"] = jwt.encode(
        {"sub": "1", "exp": expired}, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )


@when("I open the app")
def _open_app(context: dict) -> None:
    client = _bare_client()
    context["resp"] = client.get(
        _PROTECTED, headers={"Authorization": f"Bearer {context['token']}"}
    )


@then("I am asked to log in again")
def _asked_to_login_again(context: dict) -> None:
    assert context["resp"].status_code == 401
