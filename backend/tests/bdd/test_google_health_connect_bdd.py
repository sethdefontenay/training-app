"""Execute features/google_health_connect.feature via pytest-bdd (sync TestClient harness).

Covers both narratives in the file (Feature: Connect Google Health, plus the Connect
Tidepool Rule) — a single scenarios() call picks up every scenario. Interactive scenarios
that need the live Google OAuth browser flow (or a live Tidepool API) are skipped.
"""

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, scenarios, then, when

scenarios("google_health_connect.feature")

_GH = "/api/v1/settings/google-health"
_TP = "/api/v1/settings/tidepool"

_CLIENT_ID = "test-client-id.apps.googleusercontent.com"
_CLIENT_SECRET = "super-secret-value"
_REFRESH_TOKEN = "1//refresh-token-from-elsewhere"
_TP_EMAIL = "seth@example.com"
_TP_PASSWORD = "tidepool-password"


def _fields(payload: dict) -> dict[str, bool]:
    return {f["key"]: f["set"] for f in payload["fields"]}


# --- Background / shared ---


@given("I am logged in")
@given("I am on the Settings screen")
@given("I am logged in and on the Settings screen")
def _noop() -> None:
    pass  # bdd_client carries a valid owner token


# --- Google Health: starts disconnected ---


@when("I view the Google Health connection")
def _view_gh(bdd_client: TestClient, context: dict) -> None:
    resp = bdd_client.get(_GH)
    assert resp.status_code == 200
    context["gh"] = resp.json()


@then("it shows as not connected")
def _not_connected(context: dict) -> None:
    assert context["gh"]["connected"] is False


# --- Google Health: saving credentials never echoes secrets ---


@when("I save my OAuth client ID and secret")
def _save_client_creds(bdd_client: TestClient, context: dict) -> None:
    resp = bdd_client.put(_GH, json={"client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET})
    assert resp.status_code == 200
    context["gh"] = resp.json()
    context["gh_raw"] = resp.text


@then("the screen reports which fields are set")
def _reports_fields_set(context: dict) -> None:
    fields = _fields(context["gh"])
    assert fields["client_id"] is True
    assert fields["client_secret"] is True


@then("it never returns the secret values")
def _no_secret_values(context: dict) -> None:
    raw = context["gh_raw"]
    assert _CLIENT_SECRET not in raw
    assert _CLIENT_ID not in raw


# --- Google Health: Connect with Google captures a refresh token (interactive) ---


@given("I have saved my OAuth client ID and secret")
def _given_saved_creds(bdd_client: TestClient) -> None:
    resp = bdd_client.put(_GH, json={"client_id": _CLIENT_ID, "client_secret": _CLIENT_SECRET})
    assert resp.status_code == 200


@when('I tap "Connect with Google" and grant offline access')
def _tap_connect_and_grant() -> None:
    pytest.skip("interactive Google OAuth / live Google")


@then("the app stores a refresh token")
def _stores_refresh_token() -> None:
    pytest.skip("interactive Google OAuth / live Google")


@then("the connection shows as connected")
def _shows_connected(bdd_client: TestClient) -> None:
    # For the paste-token path this is reachable; the interactive path skips before here.
    resp = bdd_client.get(_GH)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True


# --- Google Health: connecting before saving client creds is refused ---


@given("I have not saved a client ID")
def _no_client_id(bdd_client: TestClient) -> None:
    # Fresh DB has no client_id; assert the precondition holds.
    assert _fields(bdd_client.get(_GH).json())["client_id"] is False


@when('I tap "Connect with Google"')
def _tap_connect(bdd_client: TestClient, context: dict) -> None:
    # authorize does a browser redirect; capture it without following.
    context["authorize"] = bdd_client.get(f"{_GH}/authorize", follow_redirects=False)


@then("I am told to save my client ID and secret first")
def _told_to_save_first(context: dict) -> None:
    resp = context["authorize"]
    # authorize guards on a missing client_id by redirecting back with gh=missing_client
    # (app/api/settings.py: _back("missing_client")), not to the Google consent screen.
    assert resp.status_code in (302, 307)
    location = resp.headers["location"]
    assert "gh=missing_client" in location
    assert "accounts.google.com" not in location


# --- Google Health: cancelled / failed consent is reported (interactive) ---


@when("the Google consent is cancelled")
def _consent_cancelled(bdd_client: TestClient, context: dict) -> None:
    # The callback reports a denied/cancelled consent via gh=denied rather than
    # silently ignoring it (app/api/settings.py: error branch -> _back("denied")).
    context["callback"] = bdd_client.get(
        f"{_GH}/callback", params={"error": "access_denied"}, follow_redirects=False
    )


@then("I am told the sign-in was cancelled")
def _told_cancelled(context: dict) -> None:
    resp = context["callback"]
    assert resp.status_code in (302, 307)
    assert "gh=denied" in resp.headers["location"]


# --- Google Health: pasting an existing refresh token also connects ---


@given("I already have a refresh token from elsewhere")
def _have_refresh_token(context: dict) -> None:
    context["refresh_token"] = _REFRESH_TOKEN


@when("I save the client ID, secret and refresh token directly")
def _save_all(bdd_client: TestClient, context: dict) -> None:
    resp = bdd_client.put(
        _GH,
        json={
            "client_id": _CLIENT_ID,
            "client_secret": _CLIENT_SECRET,
            "refresh_token": context["refresh_token"],
        },
    )
    assert resp.status_code == 200


# --- Google Health: once connected, a sync pulls steps and sleep (interactive) ---


@given("Google Health is connected")
def _gh_connected() -> None:
    pytest.skip("interactive Google OAuth / live Google")


@when("a sync runs")
def _sync_runs() -> None:
    pytest.skip("interactive Google OAuth / live Google")


@then("steps and sleep are pulled using a freshly refreshed access token")
def _steps_sleep_pulled() -> None:
    pytest.skip("interactive Google OAuth / live Google")


# --- Tidepool: save credentials and connect ---


@when("I save my Tidepool email and password")
def _save_tidepool(bdd_client: TestClient, context: dict) -> None:
    resp = bdd_client.put(_TP, json={"email": _TP_EMAIL, "password": _TP_PASSWORD})
    assert resp.status_code == 200
    context["tp"] = resp.json()
    context["tp_raw"] = resp.text


@then("Tidepool shows as connected")
def _tidepool_connected(bdd_client: TestClient) -> None:
    resp = bdd_client.get(_TP)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True


@then("the password is never returned to the client")
def _tidepool_no_password(context: dict) -> None:
    assert _TP_PASSWORD not in context["tp_raw"]


# --- Tidepool: pull glucose and insulin (needs live Tidepool API) ---


@given("Tidepool is connected")
def _tidepool_is_connected() -> None:
    pytest.skip("live Tidepool API")


@when("I pull (or a check-in runs)")
def _tidepool_pull() -> None:
    pytest.skip("live Tidepool API")


@then("the app logs in, fetches the data-model records, and stores glucose + insulin")
def _tidepool_stored() -> None:
    pytest.skip("live Tidepool API")
