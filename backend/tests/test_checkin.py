"""weekly_checkin.feature: 7-day window, metric summaries, measurements, reflections, photos."""

from datetime import date
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DailyWellbeing, Measurement, SleepNight, StepsDay, User

START = "2026-05-25"


async def _uid(session: AsyncSession) -> int:
    return int(await session.scalar(select(User.id).order_by(User.id).limit(1)))


async def test_start_uses_rolling_7_day_window(auth_client: AsyncClient) -> None:
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    assert ci["window_start"] == "2026-05-19"
    assert ci["window_end"] == "2026-05-25"


async def test_metrics_summarise_logged_days_only(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    uid = await _uid(session)
    session.add_all(
        [
            DailyWellbeing(user_id=uid, date=date(2026, 5, 19), energy=6),
            DailyWellbeing(user_id=uid, date=date(2026, 5, 20), energy=7),
            DailyWellbeing(user_id=uid, date=date(2026, 5, 21), energy=8),
            # 05-22..25 not logged -> must not count as zero
        ]
    )
    await session.commit()
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    energy = ci["metrics"]["energy"]
    assert len(energy["values"]) == 3
    assert energy["average"] == 7.0


async def test_measurements_prefill(auth_client: AsyncClient, session: AsyncSession) -> None:
    session.add(Measurement(user_id=await _uid(session), date=date(2026, 5, 25), waist_cm=96))
    await session.commit()
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    assert ci["measurements"]["waist_cm"] == 96


async def test_checkin_includes_steps_sleep_and_latest_measurements(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    uid = await _uid(session)
    session.add_all(
        [
            StepsDay(user_id=uid, date=date(2026, 5, 24), steps=6000),
            StepsDay(user_id=uid, date=date(2026, 5, 25), steps=8000),
            SleepNight(user_id=uid, date=date(2026, 5, 25), asleep_min=472.0, efficiency=98.0),
            Measurement(user_id=uid, date=date(2026, 5, 20), waist_cm=96, weight_kg=94),
        ]
    )
    await session.commit()
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    assert ci["steps_avg"] == 7000
    assert ci["sleep"]["avg_efficiency"] == 98.0
    assert ci["sleep"]["nights"] == 1
    assert ci["latest_measurements"]["waist_cm"] == 96
    assert ci["latest_measurements"]["weight_kg"] == 94


async def test_reflections_saved(auth_client: AsyncClient) -> None:
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    patched = await auth_client.patch(
        f"/api/v1/check-ins/{ci['id']}",
        json={"worked_on": "shoulder stability", "struggles": "sleep"},
    )
    body = patched.json()
    assert body["worked_on"] == "shoulder stability"
    assert body["struggles"] == "sleep"


async def test_finish_marks_complete(auth_client: AsyncClient) -> None:
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    done = await auth_client.post(f"/api/v1/check-ins/{ci['id']}/finish")
    assert done.json()["completed"] is True


async def test_photo_upload(
    auth_client: AsyncClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.api.checkin.UPLOAD_DIR", tmp_path)
    ci = (await auth_client.post("/api/v1/check-ins", json={"started_on": START})).json()
    resp = await auth_client.post(
        f"/api/v1/check-ins/{ci['id']}/photos",
        files={"file": ("front.jpg", b"\xff\xd8imagebytes", "image/jpeg")},
    )
    assert resp.status_code == 201
    saved = Path(resp.json()["storage_path"])
    assert saved.exists()
    # photo shows on the check-in
    view = (await auth_client.get(f"/api/v1/check-ins/{ci['id']}")).json()
    assert len(view["photos"]) == 1
