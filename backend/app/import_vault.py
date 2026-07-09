"""Import an Obsidian vault into the DB.

Usage: uv run python -m app.import_vault <vault_path>
(Or via invoke: `invoke import-vault --path /mnt/c/automation/Training`.)
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.importer import import_vault
from app.models import User


async def _run(path: str) -> None:
    async with SessionLocal() as session:
        owner = await session.scalar(
            select(User).where(User.is_admin.is_(True)).order_by(User.id).limit(1)
        )
        if owner is None:
            print("No admin user found — seed the owner account before importing.")
            raise SystemExit(1)
        summary = await import_vault(session, Path(path), owner.id)
    print("Imported:", summary.counts)
    if summary.failures:
        print(f"\n{len(summary.failures)} file(s) need attention:")
        for f in summary.failures:
            print("  -", f)


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.import_vault <vault_path>")
        raise SystemExit(1)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
