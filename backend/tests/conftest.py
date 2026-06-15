"""Shared test fixtures: in-memory DB + async HTTP client with DB override."""

import os
import tempfile
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import get_session
from app.main import app
from app.models import Base, User
from app.security import create_access_token, hash_password


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    # Temp-file sqlite: every connection hits the same DB (no shared-connection fragility).
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()
    os.unlink(path)


@pytest_asyncio.fixture
async def sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with sessionmaker() as s:
        yield s


@pytest_asyncio.fixture
async def client(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def _override() -> AsyncGenerator[AsyncSession, None]:
        async with sessionmaker() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def user(session: AsyncSession) -> User:
    u = User(email="seth@example.com", hashed_password=hash_password("correcthorse"))
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, user: User) -> AsyncClient:
    """A client carrying a valid bearer token for the seeded user."""
    client.headers["Authorization"] = f"Bearer {create_access_token(str(user.id))}"
    return client


@pytest_asyncio.fixture
async def trainer(session: AsyncSession) -> User:
    u = User(
        email="coach@example.com",
        hashed_password=hash_password("correcthorse"),
        role="trainer",
    )
    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


@pytest_asyncio.fixture
async def trainer_client(client: AsyncClient, trainer: User) -> AsyncClient:
    """A client carrying a valid bearer token for a read-only trainer login."""
    client.headers["Authorization"] = f"Bearer {create_access_token(str(trainer.id))}"
    return client
