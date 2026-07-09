"""Import a Tidepool data-model JSON export into the DB.

Usage: uv run python -m app.import_diabetes <file.json>
(Or via invoke: `invoke diabetes-import --file path/to/export.json`.)

The file must be a JSON array of Tidepool data-model objects (cbg/smbg/bolus/basal).
Records are de-duplicated by timestamp, so re-running is safe.
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.integrations.tidepool import parse_tidepool_export, store_points
from app.models import User


async def _run(path: str) -> None:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        print("Expected a JSON array of Tidepool data objects")
        raise SystemExit(1)
    glucose, insulin = parse_tidepool_export(data)
    async with SessionLocal() as session:
        owner = await session.scalar(
            select(User).where(User.is_admin.is_(True)).order_by(User.id).limit(1)
        )
        if owner is None:
            print("No admin user found — seed the owner account before importing.")
            raise SystemExit(1)
        g_added, i_added = await store_points(session, glucose, insulin, owner.id)
    print(f"Imported {g_added} glucose readings and {i_added} insulin events.")


def main() -> None:
    if len(sys.argv) != 2:
        print("usage: python -m app.import_diabetes <file.json>")
        raise SystemExit(1)
    asyncio.run(_run(sys.argv[1]))


if __name__ == "__main__":
    main()
