"""Shared API dependencies."""

from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import User
from app.security import decode_token

_bearer = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]

_TSel = TypeVar("_TSel", bound=tuple[Any, ...])


def owned(stmt: Select[_TSel], model: Any, user: User) -> Select[_TSel]:
    """Scope a SELECT to the given user's rows.

    The single choke point for owner isolation: every domain read passes its statement
    through here so the `user_id == user.id` filter can't be silently omitted. Fail-closed
    by construction — a query that forgets to call this returns nothing useful in the
    isolation test matrix (U11) rather than leaking another user's data.
    """
    return stmt.where(model.user_id == user.id)


# Trainers may read (GET/HEAD/OPTIONS) everything and use the assistant chat, but may
# not mutate anything and may not touch settings at all.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_TRAINER_WRITE_ALLOWLIST = frozenset({("POST", "/api/v1/assistant/chat")})


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    subject = decode_token(creds.credentials)
    if subject is None:
        raise unauthorized
    user = await session.get(User, int(subject))
    if user is None:
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def enforce_role_access(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: SessionDep,
) -> None:
    """Router-wide guard: confine trainer logins to read-only access.

    Deliberately optional-auth — if there's no/invalid token it does nothing and lets
    each endpoint's own auth decide, so unauthed routes (login, ping, the Google OAuth
    callback) keep working. The security boundary for *trainers* lives here; owners and
    anonymous requests pass straight through.
    """
    if creds is None:
        return
    subject = decode_token(creds.credentials)
    if subject is None:
        return
    user = await session.get(User, int(subject))
    if user is None or user.role != "trainer":
        return
    path = request.url.path
    if path.startswith("/api/v1/settings"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Trainer accounts cannot access settings"
        )
    if request.method in _SAFE_METHODS:
        return
    if (request.method, path) in _TRAINER_WRITE_ALLOWLIST:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Trainer accounts have read-only access"
    )
