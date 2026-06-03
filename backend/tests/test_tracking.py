"""measurements / mobility / exercise_progression features."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, SetEntry
from app.services.workouts import get_or_create_exercise


async def _seed_session(
    session: AsyncSession, slug: str, day: date, sets: list[tuple[str | None, str]]
) -> None:
    ex = await get_or_create_exercise(session, slug)
    s = Session(date=day, weekday=day.strftime("%A"))
    session.add(s)
    await session.flush()
    for i, (weight, reps) in enumerate(sets, start=1):
        session.add(
            SetEntry(session_id=s.id, exercise_id=ex.id, set_index=i, reps=reps, weight=weight)
        )
    await session.commit()


# --- measurements ---


async def test_record_and_list_measurements(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        "/api/v1/measurements",
        json={"date": "2026-05-25", "waist_cm": 96, "weight_kg": 94},
    )
    assert resp.status_code == 200
    listed = await auth_client.get("/api/v1/measurements")
    assert len(listed.json()) == 1
    assert listed.json()[0]["waist_cm"] == 96


async def test_record_partial_leaves_others_blank(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/v1/measurements", json={"date": "2026-05-26", "weight_kg": 93})
    row = (await auth_client.get("/api/v1/measurements/2026-05-26")).json()
    assert row["weight_kg"] == 93
    assert row["waist_cm"] is None


async def test_change_since_previous(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/v1/measurements", json={"date": "2026-05-18", "waist_cm": 98})
    await auth_client.post("/api/v1/measurements", json={"date": "2026-05-25", "waist_cm": 96})
    row = (await auth_client.get("/api/v1/measurements/2026-05-25")).json()
    assert row["changes"]["waist_cm"] == -2


async def test_edit_measurement_no_duplicate(auth_client: AsyncClient) -> None:
    await auth_client.post("/api/v1/measurements", json={"date": "2026-05-25", "weight_kg": 94})
    await auth_client.post("/api/v1/measurements", json={"date": "2026-05-25", "weight_kg": 93.5})
    listed = (await auth_client.get("/api/v1/measurements")).json()
    assert len(listed) == 1
    assert listed[0]["weight_kg"] == 93.5


# --- mobility ---


async def test_mark_and_list_mobility_done(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/v1/mobility/done", json={"date": "2026-05-22", "exercise_slug": "bird-dog"}
    )
    assert r.status_code == 201
    # idempotent
    await auth_client.post(
        "/api/v1/mobility/done", json={"date": "2026-05-22", "exercise_slug": "bird-dog"}
    )
    done = (await auth_client.get("/api/v1/mobility/done", params={"on": "2026-05-22"})).json()
    assert done == ["bird-dog"]


async def test_mobility_can_be_unmarked(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/mobility/done", json={"date": "2026-05-22", "exercise_slug": "bird-dog"}
    )
    await auth_client.delete(
        "/api/v1/mobility/done", params={"on": "2026-05-22", "exercise_slug": "bird-dog"}
    )
    done = (await auth_client.get("/api/v1/mobility/done", params={"on": "2026-05-22"})).json()
    assert done == []


# --- progression ---


async def test_progression_weighted_oldest_to_newest(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "leg-press-machine", date(2026, 5, 11), [("35", "15")])
    await _seed_session(session, "leg-press-machine", date(2026, 5, 18), [("40", "15")])
    points = (await auth_client.get("/api/v1/exercises/leg-press-machine/progression")).json()
    assert [p["display"] for p in points] == ["35 kg", "40 kg"]


async def test_progression_bodyweight_tracks_reps(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "crunches", date(2026, 5, 18), [(None, "15"), (None, "18")])
    points = (await auth_client.get("/api/v1/exercises/crunches/progression")).json()
    assert points[0]["display"] == "18 reps"


async def test_progression_no_history_empty(auth_client: AsyncClient) -> None:
    points = (await auth_client.get("/api/v1/exercises/hip-thrust/progression")).json()
    assert points == []
