"""Phase 0 walking-skeleton: prove the service boots and answers."""

from httpx import AsyncClient


async def test_health_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "training-app"


async def test_api_v1_ping(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": "ok"}
