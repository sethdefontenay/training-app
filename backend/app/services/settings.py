"""UI-managed integration settings (currently Google Health connection config)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IntegrationSetting

GOOGLE_HEALTH_FIELDS = (("api_key", "Google Health API key"),)


async def get_setting(session: AsyncSession, key: str) -> str | None:
    row = await session.scalar(select(IntegrationSetting).where(IntegrationSetting.key == key))
    return row.value if row else None


async def set_setting(session: AsyncSession, key: str, value: str | None) -> None:
    row = await session.scalar(select(IntegrationSetting).where(IntegrationSetting.key == key))
    if row is None:
        row = IntegrationSetting(key=key)
        session.add(row)
    row.value = value or None


async def google_health_config(session: AsyncSession) -> dict[str, str | None]:
    return {f: await get_setting(session, f"google_health.{f}") for f, _ in GOOGLE_HEALTH_FIELDS}


async def google_health_connected(session: AsyncSession) -> bool:
    return bool(await get_setting(session, "google_health.api_key"))
