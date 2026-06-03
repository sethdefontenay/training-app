"""Settings: UI-managed Google Health connection (API key)."""

from httpx import AsyncClient


async def test_starts_disconnected(auth_client: AsyncClient) -> None:
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert s["connected"] is False


async def test_save_then_connected(auth_client: AsyncClient) -> None:
    await auth_client.put("/api/v1/settings/google-health", json={"api_key": "key-123"})
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert s["connected"] is True
    field = next(f for f in s["fields"] if f["key"] == "api_key")
    assert field["set"] is True


async def test_secrets_not_echoed(auth_client: AsyncClient) -> None:
    await auth_client.put("/api/v1/settings/google-health", json={"api_key": "sekret-value"})
    s = (await auth_client.get("/api/v1/settings/google-health")).json()
    assert "sekret-value" not in str(s)  # only 'set' booleans, never the secret
