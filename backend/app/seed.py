"""Create or reset the single user. Usage: uv run python -m app.seed <email> <password>"""

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
        else:
            session.add(User(email=email, hashed_password=hash_password(password)))
        await session.commit()


def main() -> None:
    if len(sys.argv) != 3:
        print("usage: python -m app.seed <email> <password>")
        raise SystemExit(1)
    asyncio.run(create_user(sys.argv[1], sys.argv[2]))
    print(f"user {sys.argv[1]} created/updated")


if __name__ == "__main__":
    main()
