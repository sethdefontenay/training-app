"""Import an Obsidian vault into the DB.

Usage: uv run python -m app.import_vault <vault_path>
(Or via invoke: `invoke import-vault --path /mnt/c/automation/Training`.)
"""

import asyncio
import sys
from pathlib import Path

from app.database import SessionLocal
from app.importer import import_vault


async def _run(path: str) -> None:
    async with SessionLocal() as session:
        summary = await import_vault(session, Path(path))
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
