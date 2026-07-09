"""Invite-only provisioning: admin mints codes, registration consumes them once."""

from httpx import AsyncClient


async def _mint(auth_client: AsyncClient, email: str | None = None) -> str:
    resp = await auth_client.post("/api/v1/invites", json={"email": email})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["used"] is False
    return str(body["code"])


async def test_admin_mints_and_lists_invites(auth_client: AsyncClient) -> None:
    code = await _mint(auth_client)
    listed = (await auth_client.get("/api/v1/invites")).json()
    assert any(i["code"] == code for i in listed)


async def test_valid_code_creates_standard_user(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    code = await _mint(auth_client)
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "newbie@example.com", "password": "correcthorse", "code": code},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    # The new user is a standard user: capability flags off.
    client.headers["Authorization"] = f"Bearer {token}"
    me = (await client.get("/api/v1/auth/me")).json()
    assert me["email"] == "newbie@example.com"
    assert me["is_admin"] is False
    assert me["has_diabetes"] is False


async def test_code_is_single_use(auth_client: AsyncClient, client: AsyncClient) -> None:
    code = await _mint(auth_client)
    first = await client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "correcthorse", "code": code},
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/auth/register",
        json={"email": "b@example.com", "password": "correcthorse", "code": code},
    )
    assert second.status_code == 400


async def test_unknown_code_rejected(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "x@example.com", "password": "correcthorse", "code": "nope"},
    )
    assert resp.status_code == 400


async def test_email_bound_invite_rejects_mismatch(
    auth_client: AsyncClient, client: AsyncClient
) -> None:
    code = await _mint(auth_client, email="invited@example.com")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "someone.else@example.com", "password": "correcthorse", "code": code},
    )
    assert resp.status_code == 400


async def test_non_admin_cannot_mint(other_client: AsyncClient) -> None:
    assert (await other_client.post("/api/v1/invites", json={"email": None})).status_code == 403
