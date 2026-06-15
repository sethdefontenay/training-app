"""Trainer (read-only coach) access: reads + chat allowed, writes + settings blocked."""

from httpx import AsyncClient

from app.assistant.tools import TOOLS, anthropic_tools

# --- backend access boundary ---


async def test_owner_role_reported_by_me(auth_client: AsyncClient) -> None:
    body = (await auth_client.get("/api/v1/auth/me")).json()
    assert body["role"] == "owner"


async def test_trainer_role_reported_by_me(trainer_client: AsyncClient) -> None:
    body = (await trainer_client.get("/api/v1/auth/me")).json()
    assert body["role"] == "trainer"


async def test_trainer_can_read(trainer_client: AsyncClient) -> None:
    assert (await trainer_client.get("/api/v1/sessions")).status_code == 200
    assert (await trainer_client.get("/api/v1/daily/2026-05-25")).status_code == 200


async def test_trainer_cannot_post(trainer_client: AsyncClient) -> None:
    resp = await trainer_client.post("/api/v1/sessions", json={"date": "2026-05-25"})
    assert resp.status_code == 403


async def test_trainer_cannot_put(trainer_client: AsyncClient) -> None:
    resp = await trainer_client.put("/api/v1/daily/2026-05-25/wellbeing", json={"energy": 5})
    assert resp.status_code == 403


async def test_trainer_cannot_delete(trainer_client: AsyncClient) -> None:
    assert (await trainer_client.delete("/api/v1/sets/1")).status_code == 403


async def test_trainer_blocked_from_settings_even_for_reads(trainer_client: AsyncClient) -> None:
    assert (await trainer_client.get("/api/v1/settings/google-health")).status_code == 403


async def test_owner_can_still_write_and_read_settings(auth_client: AsyncClient) -> None:
    created = await auth_client.post("/api/v1/sessions", json={"date": "2026-05-25"})
    assert created.status_code == 201
    assert (await auth_client.get("/api/v1/settings/google-health")).status_code == 200


async def test_trainer_may_reach_assistant_chat(trainer_client: AsyncClient) -> None:
    # The guard must let the chat through (not 403). With no ANTHROPIC_API_KEY in tests
    # the endpoint returns 503 — which proves the request passed the read-only guard.
    resp = await trainer_client.post(
        "/api/v1/assistant/chat",
        json={"messages": [{"role": "user", "content": "hi"}]},
    )
    assert resp.status_code != 403


# --- assistant guardrails ---


async def test_read_only_toolset_excludes_writes() -> None:
    names = {t["name"] for t in anthropic_tools(include_writes=False)}
    write_names = {t.name for t in TOOLS if t.writes}
    assert write_names  # there ARE write tools to exclude
    assert names.isdisjoint(write_names)
    # read tools are still present
    assert "get_today" in names
