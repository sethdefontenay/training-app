"""Backfill daily water/electrolytes adherence over a date range.

Usage: python -m app.backfill_adherence <start YYYY-MM-DD> <end YYYY-MM-DD> [water_units]

Marks every day in [start, end) (end EXCLUSIVE — so it never touches today) as
water_units=<n> (default 2, i.e. "drank 2 L") and electrolytes_done=True. Upserts by
date, so re-running is idempotent and won't clobber an existing higher water count.
"""

import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import select

from app.database import SessionLocal
from app.models import DailyLog


async def backfill(start: date, end: date, water_units: int = 2) -> int:
    """Fill [start, end) inclusive of start, exclusive of end. Returns rows touched."""
    touched = 0
    async with SessionLocal() as session:
        day = start
        while day < end:
            row = await session.scalar(select(DailyLog).where(DailyLog.date == day))
            if row is None:
                session.add(DailyLog(date=day, water_units=water_units, electrolytes_done=True))
            else:
                row.water_units = max(row.water_units, water_units)
                row.electrolytes_done = True
            touched += 1
            day += timedelta(days=1)
        await session.commit()
    return touched


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print("usage: python -m app.backfill_adherence <start> <end-exclusive> [water_units]")
        raise SystemExit(1)
    start = date.fromisoformat(sys.argv[1])
    end = date.fromisoformat(sys.argv[2])
    water_units = int(sys.argv[3]) if len(sys.argv) == 4 else 2
    n = asyncio.run(backfill(start, end, water_units))
    print(f"backfilled {n} day(s) [{start} .. {end}) water_units={water_units}, electrolytes=True")


if __name__ == "__main__":
    main()
