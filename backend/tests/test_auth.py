"""Auth behaviour (auth.feature): login, rejection, protected routes, token validity."""

from httpx import AsyncClient

from app.models import User
from app.security import create_access_token


async def test_login_with_correct_credentials_grants_access(
    client: AsyncClient, user: User
) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "seth@example.com", "password": "correcthorse"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_wrong_password_is_rejected(client: AsyncClient, user: User) -> None:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "seth@example.com", "password": "nope"},
    )
    assert resp.status_code == 401


async def test_protected_route_requires_login(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_protected_route_with_token(auth_client: AsyncClient, user: User) -> None:
    resp = await auth_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "seth@example.com"


async def test_garbage_token_is_rejected(client: AsyncClient) -> None:
    client.headers["Authorization"] = "Bearer not-a-real-token"
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_login_round_trip_then_use_token(client: AsyncClient, user: User) -> None:
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "seth@example.com", "password": "correcthorse"},
    )
    token = login.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200


async def test_unknown_user_token_is_rejected(client: AsyncClient) -> None:
    # Valid signature, but the user id doesn't exist.
    client.headers["Authorization"] = f"Bearer {create_access_token('999999')}"
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401
