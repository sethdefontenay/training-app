"""Sleep analysis: stage parsing, per-night hypnogram view, weekly trend."""

from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import local_today
from app.integrations.health import _parse_sleep
from app.models import SleepNight


def test_parse_sleep_captures_stages_and_totals() -> None:
    # NZ offset (+12h). Times are UTC; local = +12h.
    body = {
        "dataPoints": [
            {
                "sleep": {
                    "interval": {
                        "startTime": "2026-05-24T10:00:00Z",
                        "endTime": "2026-05-24T11:20:00Z",
                        "startUtcOffset": "43200s",
                        "endUtcOffset": "43200s",
                    },
                    "stages": [
                        {
                            "type": "LIGHT",
                            "startTime": "2026-05-24T10:00:00Z",
                            "endTime": "2026-05-24T10:30:00Z",
                        },
                        {
                            "type": "DEEP",
                            "startTime": "2026-05-24T10:30:00Z",
                            "endTime": "2026-05-24T11:00:00Z",
                        },
                        {
                            "type": "REM",
                            "startTime": "2026-05-24T11:00:00Z",
                            "endTime": "2026-05-24T11:20:00Z",
                        },
                    ],
                }
            }
        ]
    }
    rec = _parse_sleep(body)
    assert rec is not None
    assert rec.light_min == 30 and rec.deep_min == 30 and rec.rem_min == 20
    assert rec.asleep_min == 80
    assert rec.bedtime == "22:00" and rec.wake_time == "23:20"
    assert rec.stages is not None and len(rec.stages) == 3
    assert rec.stages[0]["type"] == "light"
    assert rec.stages[0]["start"] == "2026-05-24T22:00:00"  # localised


async def test_night_view_returns_segments(auth_client: AsyncClient, session: AsyncSession) -> None:
    session.add(
        SleepNight(
            date=date(2026, 5, 24),
            bedtime="22:00",
            wake_time="06:00",
            asleep_min=420,
            light_min=240,
            deep_min=90,
            rem_min=90,
            efficiency=92.0,
            stages=[
                {"type": "deep", "start": "2026-05-24T22:00:00", "end": "2026-05-24T22:30:00"},
                {"type": "light", "start": "2026-05-24T22:30:00", "end": "2026-05-24T23:00:00"},
            ],
        )
    )
    await session.commit()
    body = (await auth_client.get("/api/v1/sleep/night?date=2026-05-24")).json()
    assert body["found"] is True
    assert body["deep_min"] == 90
    assert [s["type"] for s in body["segments"]] == ["deep", "light"]
    assert body["segments"][0]["start_min"] == 0
    assert body["segments"][1]["start_min"] == 30  # 30 min after the first stage


async def test_night_view_missing(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/api/v1/sleep/night?date=2020-01-01")).json()["found"] is False


async def test_trend_averages(auth_client: AsyncClient, session: AsyncSession) -> None:
    # Seed within the trend window relative to today (fixed dates drift out of range over time).
    d1, d2 = local_today() - timedelta(days=2), local_today() - timedelta(days=1)
    session.add(SleepNight(date=d1, asleep_min=400, efficiency=90.0, deep_min=80))
    session.add(SleepNight(date=d2, asleep_min=440, efficiency=94.0, deep_min=100))
    await session.commit()
    body = (await auth_client.get("/api/v1/sleep/trend?days=30")).json()
    assert body["averages"]["asleep_min"] == 420.0
    assert body["averages"]["efficiency"] == 92.0
    assert body["averages"]["deep_min"] == 90.0
    assert body["averages"]["count"] == 2
