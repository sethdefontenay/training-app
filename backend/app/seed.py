"""Create or reset a user. Usage: uv run python -m app.seed <email> <password> [role]

role is "owner" (default, full access) or "trainer" (read-only coach login).
"""

import asyncio
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password


async def create_user(email: str, password: str, role: str = "owner") -> None:
    async with SessionLocal() as session:
        existing = await session.scalar(select(User).where(User.email == email))
        if existing is not None:
            existing.hashed_password = hash_password(password)
            existing.role = role
        else:
            session.add(User(email=email, hashed_password=hash_password(password), role=role))
        await session.commit()


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print("usage: python -m app.seed <email> <password> [role]")
        raise SystemExit(1)
    role = sys.argv[3] if len(sys.argv) == 4 else "owner"
    if role not in ("owner", "trainer"):
        print(f"role must be 'owner' or 'trainer', got {role!r}")
        raise SystemExit(1)
    asyncio.run(create_user(sys.argv[1], sys.argv[2], role))
    print(f"{role} {sys.argv[1]} created/updated")


if __name__ == "__main__":
    main()
