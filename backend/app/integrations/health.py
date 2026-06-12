"""Steps + sleep sync (ported from google-health / catch_up.py).

The provider boundary is abstracted so it can be mocked in tests and swapped for the
real Google Health client once credentials are wired. The sync itself is idempotent and
never silently overwrites a manual entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SleepNight, StepsDay

# Google Health API (v4) — same endpoints the standalone google-health-fetch uses.
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_STEPS_URL = "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:rollUp"
_SLEEP_URL = "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints"
_DEFAULT_TZ = "Pacific/Auckland"


def _sum_steps(body: dict[str, Any]) -> int:
    total = 0
    for point in body.get("rollupDataPoints", []):
        steps = point.get("steps", {})
        total += int(steps.get("countSum") or steps.get("count") or 0)
    return total


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_sleep(body: dict[str, Any]) -> SleepRecord | None:
    """Pick the longest sleep session and summarise it (mirrors fetch_sleep.py)."""
    points = body.get("dataPoints", [])
    if not points:
        return None

    def duration(p: dict[str, Any]) -> timedelta:
        i = p["sleep"]["interval"]
        return _parse_iso(i["endTime"]) - _parse_iso(i["startTime"])

    main = max(points, key=duration)
    interval = main["sleep"]["interval"]
    start_utc, end_utc = _parse_iso(interval["startTime"]), _parse_iso(interval["endTime"])
    start_off = int(str(interval["startUtcOffset"]).rstrip("s"))
    end_off = int(str(interval["endUtcOffset"]).rstrip("s"))
    start_local = start_utc + timedelta(seconds=start_off)
    end_local = end_utc + timedelta(seconds=end_off)

    totals = {"AWAKE": 0.0, "LIGHT": 0.0, "DEEP": 0.0, "REM": 0.0, "OUT_OF_BED": 0.0}
    segments: list[dict[str, str]] = []
    for stage in main["sleep"].get("stages", []):
        kind = stage.get("type", "")
        s_utc, e_utc = _parse_iso(stage["startTime"]), _parse_iso(stage["endTime"])
        totals[kind] = totals.get(kind, 0.0) + (e_utc - s_utc).total_seconds() / 60
        # Localise with the session offset (constant through the night) for the timeline.
        # Store as naive local wall-clock ISO (no misleading UTC suffix).
        s_local = (s_utc + timedelta(seconds=start_off)).replace(tzinfo=None)
        e_local = (e_utc + timedelta(seconds=start_off)).replace(tzinfo=None)
        segments.append(
            {"type": kind.lower(), "start": s_local.isoformat(), "end": e_local.isoformat()}
        )

    in_bed = (end_utc - start_utc).total_seconds() / 60
    asleep = totals["LIGHT"] + totals["DEEP"] + totals["REM"]
    efficiency = round(asleep / in_bed * 100, 1) if in_bed > 0 else 0.0
    return SleepRecord(
        date=end_local.date(),
        asleep_min=round(asleep, 1),
        in_bed_min=round(in_bed, 1),
        awake_min=round(totals["AWAKE"] + totals["OUT_OF_BED"], 1),
        light_min=round(totals["LIGHT"], 1),
        deep_min=round(totals["DEEP"], 1),
        rem_min=round(totals["REM"], 1),
        efficiency=efficiency,
        bedtime=start_local.strftime("%H:%M"),
        wake_time=end_local.strftime("%H:%M"),
        stages=segments or None,
    )


class IntegrationNotConfigured(RuntimeError):
    """Raised when the real provider lacks credentials."""


class IntegrationAuthExpired(RuntimeError):
    """Raised when the stored OAuth refresh token is expired/revoked and the user
    must re-consent (Google returns 400 invalid_grant). Distinct from a missing
    config so the UI can prompt a one-tap reconnect rather than a full setup."""


@dataclass
class StepRecord:
    date: date
    steps: int
    target_steps: int | None = None


@dataclass
class SleepRecord:
    date: date
    asleep_min: float | None = None
    in_bed_min: float | None = None
    awake_min: float | None = None
    light_min: float | None = None
    deep_min: float | None = None
    rem_min: float | None = None
    efficiency: float | None = None
    bedtime: str | None = None
    wake_time: str | None = None
    stages: list[dict[str, str]] | None = None


class HealthProvider(Protocol):
    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]: ...


class GoogleHealthProvider:
    """Live Google Health client. OAuth offline access: refresh token -> access token,
    then v4 steps rollup + sleep dataPoints (ported from google-health-fetch)."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        refresh_token: str | None = None,
        tz: str = _DEFAULT_TZ,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._tz = ZoneInfo(tz)

    async def _access_token(self, client: httpx.AsyncClient) -> str:
        resp = await client.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "refresh_token": self._refresh_token,
            },
        )
        if resp.status_code == 400 and "invalid_grant" in resp.text:
            raise IntegrationAuthExpired(
                "Google Health authorization expired — reconnect in Settings"
            )
        resp.raise_for_status()
        return str(resp.json()["access_token"])

    async def fetch(self, start: date, end: date) -> tuple[list[StepRecord], list[SleepRecord]]:
        if not (self._client_id and self._client_secret and self._refresh_token):
            raise IntegrationNotConfigured("Google Health not connected — set it up in Settings")

        steps_out: list[StepRecord] = []
        sleep_out: list[SleepRecord] = []
        async with httpx.AsyncClient(timeout=30) as client:
            token = await self._access_token(client)
            headers = {"Authorization": f"Bearer {token}"}
            day = start
            while day <= end:
                start_local = datetime.combine(day, time.min, tzinfo=self._tz)
                end_local = start_local + timedelta(days=1)
                steps_resp = await client.post(
                    _STEPS_URL,
                    headers=headers,
                    json={
                        "range": {
                            "startTime": start_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "endTime": end_local.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        },
                        "windowSize": "86400s",
                    },
                )
                if steps_resp.status_code == 200:
                    steps_out.append(StepRecord(date=day, steps=_sum_steps(steps_resp.json())))

                civ_start = datetime.combine(day, time.min, tzinfo=self._tz)
                civ_end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=self._tz)
                filt = (
                    f'sleep.interval.civil_end_time >= "{civ_start.strftime("%Y-%m-%dT%H:%M:%S")}" '
                    f'AND sleep.interval.civil_end_time < "{civ_end.strftime("%Y-%m-%dT%H:%M:%S")}"'
                )
                sleep_resp = await client.get(_SLEEP_URL, headers=headers, params={"filter": filt})
                if sleep_resp.status_code == 200:
                    record = _parse_sleep(sleep_resp.json())
                    if record is not None:
                        sleep_out.append(record)
                day += timedelta(days=1)
        return steps_out, sleep_out


@dataclass
class SyncResult:
    steps_synced: int = 0
    sleep_synced: int = 0
    preserved_manual: list[str] = field(default_factory=list)


async def sync_steps_sleep(
    session: AsyncSession, provider: HealthProvider, start: date, end: date
) -> SyncResult:
    steps, sleeps = await provider.fetch(start, end)
    result = SyncResult()

    for rec in steps:
        row = await session.scalar(select(StepsDay).where(StepsDay.date == rec.date))
        if row is not None and row.manual:
            result.preserved_manual.append(rec.date.isoformat())
            continue
        if row is None:
            row = StepsDay(date=rec.date)
            session.add(row)
        row.steps = rec.steps
        if rec.target_steps is not None:
            row.target_steps = rec.target_steps
            row.target_met = rec.steps >= rec.target_steps
        result.steps_synced += 1

    for night in sleeps:
        srow = await session.scalar(select(SleepNight).where(SleepNight.date == night.date))
        if srow is not None and srow.manual:
            continue
        if srow is None:
            srow = SleepNight(date=night.date)
            session.add(srow)
        srow.asleep_min = night.asleep_min
        srow.in_bed_min = night.in_bed_min
        srow.awake_min = night.awake_min
        srow.light_min = night.light_min
        srow.deep_min = night.deep_min
        srow.rem_min = night.rem_min
        srow.efficiency = night.efficiency
        srow.bedtime = night.bedtime
        srow.wake_time = night.wake_time
        srow.stages = night.stages
        result.sleep_synced += 1

    await session.commit()
    return result
