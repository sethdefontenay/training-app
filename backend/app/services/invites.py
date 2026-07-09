"""Invite-only provisioning: mint single-use codes and redeem them into new users."""

import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Invite, User
from app.security import hash_password


class EmailTaken(ValueError):
    """The registrant's email already has an account."""


async def mint_invite(session: AsyncSession, created_by: int, email: str | None = None) -> Invite:
    inv = Invite(code=secrets.token_urlsafe(16), email=email, created_by=created_by)
    session.add(inv)
    await session.commit()
    await session.refresh(inv)
    return inv


async def redeem_invite(session: AsyncSession, code: str, email: str, password: str) -> User | None:
    """Consume a single-use code and create a standard user (capability flags off).

    Returns None if the code is unknown, already used, or bound to a different email.
    Raises EmailTaken if the email already has an account. The claim is atomic
    (UPDATE ... WHERE used_at IS NULL), so two concurrent redemptions of one code create
    at most one account.
    """
    inv = await session.scalar(select(Invite).where(Invite.code == code))
    if inv is None or inv.used_at is not None:
        return None
    if inv.email is not None and inv.email.lower() != email.lower():
        return None
    if await session.scalar(select(User).where(User.email == email)) is not None:
        raise EmailTaken(email)

    now = datetime.now(UTC)
    claimed = await session.execute(
        update(Invite)
        .where(Invite.code == code, Invite.used_at.is_(None))
        .values(used_at=now)
        .returning(Invite.id)
    )
    if claimed.first() is None:
        return None  # lost a concurrent claim

    user = User(email=email, hashed_password=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
