"""Create or reset the owner account. Usage: uv run python -m app.seed <email> <password>

Creates (or resets the password of) the admin owner: is_admin plus all capability flags
on. Invited standard users are created via the registration flow, not this script.
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


async def create_user(email: str, password: str) -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            existing.hashed_password = hash_password(password)
            existing.is_admin = True
            existing.has_diabetes = True
            existing.has_health_integrations = True
            existing.has_checkins = True
        else:
            session.add(
                User(
                    email=email,
                    hashed_password=hash_password(password),
                    is_admin=True,
                    has_diabetes=True,
                    has_health_integrations=True,
                    has_checkins=True,
                )
            )
        await session.commit()


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m app.seed <email> <password>")
        raise SystemExit(1)
    asyncio.run(create_user(sys.argv[1], sys.argv[2]))
    print(f"owner {sys.argv[1]} created/updated")


if __name__ == "__main__":
    main()
