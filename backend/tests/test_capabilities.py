"""Per-user capability gating: owner-only surfaces (T1D, health integrations, check-ins)
are denied to a standard invited user (flags off) and reachable by the owner (flags on)."""

from httpx import AsyncClient

# (path, method) pairs on the three owner-only surfaces.
_DIABETES = ("/api/v1/diabetes/record", "get")
_HEALTH = [
    ("/api/v1/settings/google-health", "get"),
    ("/api/v1/sleep/night", "get"),
]
_CHECKINS = ("/api/v1/check-ins", "get")


async def test_me_reports_capability_flags(
    auth_client: AsyncClient, other_client: AsyncClient
) -> None:
    owner = (await auth_client.get("/api/v1/auth/me")).json()
    assert owner["is_admin"] is True
    assert owner["has_diabetes"] is True
    assert owner["has_health_integrations"] is True
    assert owner["has_checkins"] is True

    standard = (await other_client.get("/api/v1/auth/me")).json()
    assert standard["is_admin"] is False
    assert standard["has_diabetes"] is False
    assert standard["has_health_integrations"] is False
    assert standard["has_checkins"] is False


async def test_standard_user_denied_diabetes(other_client: AsyncClient) -> None:
    assert (await other_client.get(_DIABETES[0])).status_code == 403


async def test_standard_user_denied_health(other_client: AsyncClient) -> None:
    for path, _ in _HEALTH:
        assert (await other_client.get(path)).status_code == 403


async def test_standard_user_denied_checkins(other_client: AsyncClient) -> None:
    assert (await other_client.get(_CHECKINS[0])).status_code == 403
    assert (
        await other_client.post("/api/v1/check-ins", json={"started_on": "2026-05-25"})
    ).status_code == 403


async def test_owner_reaches_owner_only_surfaces(auth_client: AsyncClient) -> None:
    # Not 403 — the owner's flags are on. (Integrations may 200 or 503 w/o creds, but
    # never a capability 403.)
    assert (await auth_client.get(_DIABETES[0])).status_code != 403
    assert (await auth_client.get(_CHECKINS[0])).status_code == 200
    for path, _ in _HEALTH:
        assert (await auth_client.get(path)).status_code != 403


async def test_google_oauth_endpoints_are_unauthenticated(client: AsyncClient) -> None:
    # The Reconnect button and Google's callback are top-level browser navigations that
    # cannot carry a bearer token, so authorize/callback must NOT sit behind the auth or
    # capability gate. They redirect (missing_client / denied), never 401/403.
    r = await client.get("/api/v1/settings/google-health/authorize", follow_redirects=False)
    assert r.status_code not in (401, 403), r.status_code
    c = await client.get(
        "/api/v1/settings/google-health/callback?error=denied", follow_redirects=False
    )
    assert c.status_code not in (401, 403), c.status_code


async def test_standard_user_keeps_universal_surface(other_client: AsyncClient) -> None:
    # Workouts, daily, measurements, shopping remain available to every user.
    assert (await other_client.get("/api/v1/sessions")).status_code == 200
    assert (await other_client.get("/api/v1/daily/2026-05-25")).status_code == 200
    assert (await other_client.get("/api/v1/measurements")).status_code == 200
