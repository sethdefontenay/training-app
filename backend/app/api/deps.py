"""Shared API dependencies."""

from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException, status
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


async def admin_only(user: CurrentUser) -> User:
    """Guard for admin-only routes (invite minting, user provisioning). Fail-closed."""
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


AdminUser = Annotated[User, Depends(admin_only)]


def require_capability(flag: str) -> Callable[[User], Awaitable[None]]:
    """Build a router-wide dependency that 403s unless the user's capability flag is set.

    Capability flags (has_diabetes, has_health_integrations, has_checkins) default off, so
    a newly invited user is denied the owner-only surfaces until explicitly granted.
    """

    async def _dep(user: CurrentUser) -> None:
        if not getattr(user, flag, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This feature is not enabled for your account",
            )

    return _dep
