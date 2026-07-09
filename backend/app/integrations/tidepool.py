"""Diabetes data (Dexcom glucose + Tandem pump) via Tidepool.

Single integration boundary, mockable for tests. Stored to Seth's OWN record (not the
PT package). Pulled at check-in time and on opening the diabetes record. A missing pump
upload is surfaced honestly (pump_uploaded=False) — never fabricated.
⚠️ Real Tidepool API auth to be verified against live docs before wiring credentials.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any, Protocol

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.health import IntegrationNotConfigured
from app.models import GlucoseReading, InsulinEvent

_TIDEPOOL_BASE = "https://api.tidepool.org"

# Standard CGM time-in-range band (mmol/L).
TIR_LOW = 3.9
TIR_HIGH = 10.0


@dataclass
class GlucosePoint:
    ts: datetime
    mmol_l: float


@dataclass
class InsulinPoint:
    ts: datetime
    kind: str
    units: float
    carbs_g: float | None = None


class TidepoolProvider(Protocol):
    async def fetch(
        self, start: date, end: date
    ) -> tuple[list[GlucosePoint], list[InsulinPoint]]: ...


class TidepoolClient:
    """Live Tidepool API client: login (session token) -> GET /data -> parse.

    Uses the session-token auth flow (still works as a proxy post-Keycloak). Returns the
    same data-model objects parse_tidepool_export() handles.
    """

    def __init__(
        self, email: str | None = None, password: str | None = None, base_url: str = _TIDEPOOL_BASE
    ) -> None:
        self._email = email
        self._password = password
        self._base = base_url

    async def fetch(self, start: date, end: date) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
        if not (self._email and self._password):
            raise IntegrationNotConfigured("Tidepool credentials not set — add them in Settings")
        async with httpx.AsyncClient(timeout=60) as client:
            login = await client.post(
                f"{self._base}/auth/login", auth=(self._email, self._password)
            )
            if login.status_code != 200:
                raise IntegrationNotConfigured("Tidepool login failed — check email/password")
            token = login.headers.get("x-tidepool-session-token")
            userid = login.json().get("userid")
            if not token or not userid:
                raise IntegrationNotConfigured("Tidepool login returned no session token")
            resp = await client.get(
                f"{self._base}/data/{userid}",
                headers={"x-tidepool-session-token": token},
                params={
                    "startDate": f"{start.isoformat()}T00:00:00.000Z",
                    "endDate": f"{end.isoformat()}T23:59:59.999Z",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if not isinstance(data, list):
            return [], []
        return parse_tidepool_export(data)


@dataclass
class DiabetesSyncResult:
    glucose: int
    insulin: int
    pump_uploaded: bool


def _bounds(start: date, end: date) -> tuple[datetime, datetime]:
    return datetime.combine(start, time.min), datetime.combine(end, time.max)


async def sync_diabetes(
    session: AsyncSession, provider: TidepoolProvider, start: date, end: date, user_id: int
) -> DiabetesSyncResult:
    glucose, insulin = await provider.fetch(start, end)
    lo, hi = _bounds(start, end)
    # Idempotent: clear THIS user's window, then insert the fresh pull.
    await session.execute(
        delete(GlucoseReading).where(
            GlucoseReading.ts >= lo, GlucoseReading.ts <= hi, GlucoseReading.user_id == user_id
        )
    )
    await session.execute(
        delete(InsulinEvent).where(
            InsulinEvent.ts >= lo, InsulinEvent.ts <= hi, InsulinEvent.user_id == user_id
        )
    )
    for g in glucose:
        session.add(GlucoseReading(user_id=user_id, ts=_norm(g.ts), mmol_l=g.mmol_l))
    for i in insulin:
        session.add(
            InsulinEvent(
                user_id=user_id, ts=_norm(i.ts), kind=i.kind, units=i.units, carbs_g=i.carbs_g
            )
        )
    await session.commit()
    return DiabetesSyncResult(
        glucose=len(glucose), insulin=len(insulin), pump_uploaded=len(insulin) > 0
    )


async def glucose_summary(
    session: AsyncSession, start: date, end: date, user_id: int
) -> dict[str, float | int | None]:
    lo, hi = _bounds(start, end)
    values = (
        (
            await session.execute(
                select(GlucoseReading.mmol_l).where(
                    GlucoseReading.ts >= lo,
                    GlucoseReading.ts <= hi,
                    GlucoseReading.user_id == user_id,
                )
            )
        )
        .scalars()
        .all()
    )
    if not values:
        return {"average": None, "time_in_range_pct": None, "count": 0}
    in_range = [v for v in values if TIR_LOW <= v <= TIR_HIGH]
    return {
        "average": round(sum(values) / len(values), 1),
        "time_in_range_pct": round(100 * len(in_range) / len(values), 1),
        "count": len(values),
    }


_MGDL_TO_MMOL = 1 / 18.0182
UPLOAD_SOURCE = "tidepool-upload"


def parse_tidepool_export(
    data: list[dict[str, Any]],
) -> tuple[list[GlucosePoint], list[InsulinPoint]]:
    """Parse a Tidepool data-model JSON array (open-source schema) into points.

    Glucose: cbg/smbg (value + units, mg/dL converted to mmol/L). Insulin: bolus
    (normal + extended units). Times are ISO-8601 'time' fields.
    """
    glucose: list[GlucosePoint] = []
    insulin: list[InsulinPoint] = []
    for d in data:
        kind = d.get("type")
        raw_time = d.get("time")
        if not isinstance(raw_time, str):
            continue
        ts = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        if kind in ("cbg", "smbg"):
            value = d.get("value")
            if value is None:
                continue
            mmol = float(value) * _MGDL_TO_MMOL if d.get("units") == "mg/dL" else float(value)
            glucose.append(GlucosePoint(ts=ts, mmol_l=round(mmol, 1)))
        elif kind == "bolus":
            units = float(d.get("normal", 0) or 0) + float(d.get("extended", 0) or 0)
            if units:
                insulin.append(InsulinPoint(ts=ts, kind="bolus", units=units))
        elif kind == "basal":
            rate = d.get("rate")
            if rate is not None:
                insulin.append(InsulinPoint(ts=ts, kind="basal", units=float(rate)))
    return glucose, insulin


def _norm(dt: datetime) -> datetime:
    """Naive-UTC, so timestamp de-dup is consistent across sqlite/postgres + re-uploads."""
    return dt.astimezone(UTC).replace(tzinfo=None) if dt.tzinfo else dt


async def store_points(
    session: AsyncSession,
    glucose: list[GlucosePoint],
    insulin: list[InsulinPoint],
    user_id: int,
) -> tuple[int, int]:
    """Insert points, de-duplicated by timestamp within THIS user's rows (re-uploads +
    incremental files safe)."""
    g_added = 0
    if glucose:
        times = [_norm(g.ts) for g in glucose]
        seen = set(
            (
                await session.execute(
                    select(GlucoseReading.ts).where(
                        GlucoseReading.ts >= min(times),
                        GlucoseReading.ts <= max(times),
                        GlucoseReading.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for gp, ts in zip(glucose, times, strict=True):
            if ts not in seen:
                session.add(
                    GlucoseReading(user_id=user_id, ts=ts, mmol_l=gp.mmol_l, source=UPLOAD_SOURCE)
                )
                seen.add(ts)
                g_added += 1
    i_added = 0
    if insulin:
        times = [_norm(e.ts) for e in insulin]
        seen = set(
            (
                await session.execute(
                    select(InsulinEvent.ts).where(
                        InsulinEvent.ts >= min(times),
                        InsulinEvent.ts <= max(times),
                        InsulinEvent.user_id == user_id,
                    )
                )
            )
            .scalars()
            .all()
        )
        for ip, ts in zip(insulin, times, strict=True):
            if ts not in seen:
                session.add(
                    InsulinEvent(
                        user_id=user_id,
                        ts=ts,
                        kind=ip.kind,
                        units=ip.units,
                        carbs_g=ip.carbs_g,
                        source=UPLOAD_SOURCE,
                    )
                )
                seen.add(ts)
                i_added += 1
    await session.commit()
    return g_added, i_added


async def insulin_count(session: AsyncSession, start: date, end: date, user_id: int) -> int:
    lo, hi = _bounds(start, end)
    rows = (
        (
            await session.execute(
                select(InsulinEvent.id).where(
                    InsulinEvent.ts >= lo, InsulinEvent.ts <= hi, InsulinEvent.user_id == user_id
                )
            )
        )
        .scalars()
        .all()
    )
    return len(rows)
