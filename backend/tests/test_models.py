"""Verify every model maps cleanly and the full schema can be created."""

from sqlalchemy.ext.asyncio import create_async_engine

from app.models import Base

EXPECTED_TABLES = {
    "user",
    "plan",
    "exercise",
    "training_day",
    "prescription",
    "weekday_schedule",
    "meal",
    "meal_ingredient",
    "session",
    "set_entry",
    "mobility_done",
    "meal_check",
    "daily_wellbeing",
    "daily_log",
    "measurement",
    "steps_day",
    "sleep_night",
    "glucose_reading",
    "insulin_event",
    "check_in",
    "check_in_photo",
    "shopping_list",
    "shopping_item",
}


async def test_full_schema_creates() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    assert set(Base.metadata.tables.keys()) >= EXPECTED_TABLES
    await engine.dispose()
