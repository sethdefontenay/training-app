"""Harness for executing the Gherkin .feature suite via pytest-bdd.

Sync Starlette TestClient (step functions don't manage an event loop). The DB is a
temp-file sqlite; tables + the owner/trainer users are seeded once via asyncio.run, and
the app's async session override opens its own connections in the TestClient loop.

Fixtures step definitions use:
  - bdd_client      : TestClient authed as the owner (full access)
  - trainer_client  : TestClient authed as the read-only trainer
  - context         : per-scenario scratch dict shared between steps
  - seed            : seed(async_fn) — runs async_fn(session) against the app DB and commits
  - seed helpers live in tests/bdd/seed.py
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Callable, Coroutine, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_session
from app.main import app
from app.models import Base, User
from app.security import create_access_token, hash_password


@pytest.fixture
def context() -> dict[str, object]:
    """Per-scenario scratch space shared between steps."""
    return {}


@pytest.fixture
def bdd_env() -> Iterator[dict[str, Any]]:
    """Temp sqlite DB + owner/trainer users; installs the app's session override."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    url = f"sqlite+aiosqlite:///{path}"

    async def _setup() -> tuple[int, int]:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as s:
            owner = User(
                email="seth@example.com", hashed_password=hash_password("pw"), role="owner"
            )
            trainer = User(
                email="coach@example.com", hashed_password=hash_password("pw"), role="trainer"
            )
            s.add_all([owner, trainer])
            await s.commit()
            await s.refresh(owner)
            await s.refresh(trainer)
            ids = (owner.id, trainer.id)
        await engine.dispose()
        return ids

    owner_id, trainer_id = asyncio.run(_setup())

    app_engine = create_async_engine(url)
    maker = async_sessionmaker(app_engine, expire_on_commit=False)

    async def _override() -> AsyncGenerator[object, None]:
        async with maker() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    yield {"url": url, "owner_id": owner_id, "trainer_id": trainer_id}
    app.dependency_overrides.clear()
    os.unlink(path)


@pytest.fixture
def bdd_client(bdd_env: dict[str, Any]) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(str(bdd_env['owner_id']))}"
    return client


@pytest.fixture
def trainer_client(bdd_env: dict[str, Any]) -> TestClient:
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {create_access_token(str(bdd_env['trainer_id']))}"
    return client


SeedFn = Callable[[AsyncSession], Coroutine[Any, Any, Any]]


@pytest.fixture
def seed(bdd_env: dict[str, Any]) -> Callable[[SeedFn], Any]:
    """Return a runner: seed(fn) executes async fn(session) against the app DB and commits.

    Usage in a step:
        from tests.bdd.seed import full_plan
        seed(full_plan)
        seed(lambda s: add_steps(s, date(2026, 5, 25), 733))
    """
    url = bdd_env["url"]

    def _run(fn: SeedFn) -> Any:
        async def _inner() -> Any:
            engine = create_async_engine(url)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            result: Any = None
            async with maker() as s:
                result = await fn(s)
                await s.commit()
            await engine.dispose()
            return result

        return asyncio.run(_inner())

    return _run
