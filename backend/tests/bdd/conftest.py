"""Sync harness for executing the Gherkin .feature suite via pytest-bdd.

Uses Starlette's TestClient (sync) so step functions don't need to manage an event
loop. The DB is a temp-file sqlite; table creation + user seed run once via asyncio.run,
and the app's async session override opens its own connections in the TestClient loop.
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, User
from app.security import create_access_token, hash_password


@pytest.fixture
def context() -> dict[str, object]:
    """Per-scenario scratch space shared between steps."""
    return {}


@pytest.fixture
def bdd_client() -> Iterator[TestClient]:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"

    async def _setup() -> int:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            user = User(email="seth@example.com", hashed_password=hash_password("pw"))
            s.add(user)
            await s.commit()
            await s.refresh(user)
            uid = user.id
        await engine.dispose()
        return uid

    uid = asyncio.run(_setup())

    app_engine = create_async_engine(url)
    maker = async_sessionmaker(app_engine, expire_on_commit=False)

    async def _override() -> AsyncGenerator[object, None]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(str(uid))}"
    yield client
    app.dependency_overrides.clear()
    os.unlink(path)
