"""Settings: UI-managed Google Health connection (OAuth: client id/secret + refresh token)."""

from httpx import AsyncClient

_CREDS = {"client_id": "cid", "client_secret": "csecret", "refresh_token": "rtok"}


async def test_starts_disconnected(auth_client: AsyncClient) -> None:
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert s["connected"] is False


async def test_partial_creds_not_connected(auth_client: AsyncClient) -> None:
    await auth_client.put("/api/v1/settings/google-health", json={"client_id": "cid"})
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert s["connected"] is False  # needs all three


async def test_full_creds_connected(auth_client: AsyncClient) -> None:
    await auth_client.put("/api/v1/settings/google-health", json=_CREDS)
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert s["connected"] is True
    assert all(f["set"] for f in s["fields"])


async def test_secrets_not_echoed(auth_client: AsyncClient) -> None:
    await auth_client.put(
        "/api/v1/settings/google-health", json={"refresh_token": "super-secret-token"}
    )
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert "super-secret-token" not in str(s)
