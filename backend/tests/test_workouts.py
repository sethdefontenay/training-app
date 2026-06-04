"""workout_logging.feature: logging, bodyweight, edit/delete, and the last-week column."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session, SetEntry
from app.services.workouts import get_or_create_exercise


async def _seed_session(
    session: AsyncSession, slug: str, day: date, sets: list[tuple[str | None, str]]
) -> None:
    """Seed a prior session with (weight, reps) tuples; weight None = bodyweight."""
    ex = await get_or_create_exercise(session, slug)
    s = Session(date=day, weekday=day.strftime("%A"))
    session.add(s)
    await session.flush()
    for i, (weight, reps) in enumerate(sets, start=1):
        session.add(
            SetEntry(session_id=s.id, exercise_id=ex.id, set_index=i, reps=reps, weight=weight)
        )
    await session.commit()


async def _new_session(auth_client: AsyncClient, day: str = "2026-05-25") -> int:
    resp = await auth_client.post("/api/v1/sessions", json={"date": day})
    assert resp.status_code == 201
    return int(resp.json()["id"])


# --- logging ---


async def test_log_resistance_set(auth_client: AsyncClient) -> None:
    sid = await _new_session(auth_client)
    resp = await auth_client.post(
        f"/api/v1/sessions/{sid}/sets",
        json={"exercise_slug": "leg-press-machine", "reps": "15", "weight": "40"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["display"] == "40 kg × 15"
    assert body["set_index"] == 1


async def test_log_bodyweight_set(auth_client: AsyncClient) -> None:
    sid = await _new_session(auth_client)
    resp = await auth_client.post(
        f"/api/v1/sessions/{sid}/sets",
        json={"exercise_slug": "crunches", "reps": "15", "weight": ""},
    )
    assert resp.status_code == 201
    assert resp.json()["display"] == "BW × 15"


async def test_edit_set_does_not_create_extra(auth_client: AsyncClient) -> None:
    sid = await _new_session(auth_client)
    created = await auth_client.post(
        f"/api/v1/sessions/{sid}/sets",
        json={"exercise_slug": "leg-press-machine", "reps": "15", "weight": "40"},
    )
    set_id = created.json()["id"]
    edited = await auth_client.patch(f"/api/v1/sets/{set_id}", json={"reps": "12", "weight": "45"})
    assert edited.status_code == 200
    assert edited.json()["display"] == "45 kg × 12"

    detail = await auth_client.get(f"/api/v1/sessions/{sid}")
    assert len(detail.json()["sets"]) == 1


async def test_delete_set(auth_client: AsyncClient) -> None:
    sid = await _new_session(auth_client)
    created = await auth_client.post(
        f"/api/v1/sessions/{sid}/sets",
        json={"exercise_slug": "leg-press-machine", "reps": "15", "weight": "40"},
    )
    set_id = created.json()["id"]
    resp = await auth_client.delete(f"/api/v1/sets/{set_id}")
    assert resp.status_code == 204
    detail = await auth_client.get(f"/api/v1/sessions/{sid}")
    assert detail.json()["sets"] == []


# --- last-week column ---


async def _last_week(auth_client: AsyncClient, slug: str, before: str) -> str:
    resp = await auth_client.get(f"/api/v1/exercises/{slug}/last-week", params={"before": before})
    assert resp.status_code == 200
    return str(resp.json()["display"])


async def test_last_week_heaviest_weight(auth_client: AsyncClient, session: AsyncSession) -> None:
    await _seed_session(session, "leg-press-machine", date(2026, 5, 18), [("40", "15")])
    assert await _last_week(auth_client, "leg-press-machine", "2026-05-25") == "40 kg"


async def test_last_week_most_recent_prior_not_seven_days(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "lat-pulldown", date(2026, 5, 15), [("47", "15")])
    assert await _last_week(auth_client, "lat-pulldown", "2026-05-25") == "47 kg"


async def test_last_week_only_heaviest_regardless_of_reps(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(
        session,
        "leg-press-machine",
        date(2026, 5, 18),
        [("40", "15"), ("45", "12"), ("45", "14")],
    )
    assert await _last_week(auth_client, "leg-press-machine", "2026-05-25") == "45 kg"


async def test_last_week_bodyweight_shows_bw(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "crunches", date(2026, 5, 18), [(None, "15")])
    assert await _last_week(auth_client, "crunches", "2026-05-25") == "BW"


async def test_last_week_no_history_shows_dash(auth_client: AsyncClient) -> None:
    assert await _last_week(auth_client, "hip-thrust", "2026-05-25") == "—"


async def test_last_week_excludes_todays_own_sets(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "leg-press-machine", date(2026, 5, 18), [("40", "15")])
    await _seed_session(session, "leg-press-machine", date(2026, 5, 25), [("45", "15")])
    # before=today (2026-05-25) excludes today's own sets -> shows the prior session
    assert await _last_week(auth_client, "leg-press-machine", "2026-05-25") == "40 kg"


# --- exercise progress over time ---


async def test_progress_series_weight_over_time(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(
        session, "leg-press-machine", date(2026, 5, 11), [("40", "15"), ("40", "12")]
    )
    await _seed_session(session, "leg-press-machine", date(2026, 5, 18), [("45", "15")])
    await _seed_session(
        session, "leg-press-machine", date(2026, 5, 25), [("50", "10"), ("45", "15")]
    )
    body = (await auth_client.get("/api/v1/exercises/leg-press-machine/progress")).json()
    assert body["metric"] == "weight"
    assert [(p["date"], p["weight"]) for p in body["points"]] == [
        ("2026-05-11", 40.0),
        ("2026-05-18", 45.0),
        ("2026-05-25", 50.0),  # heaviest set that day
    ]


async def test_progress_ties_broken_by_reps(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(
        session, "leg-press-machine", date(2026, 5, 25), [("50", "8"), ("50", "12")]
    )
    body = (await auth_client.get("/api/v1/exercises/leg-press-machine/progress")).json()
    assert body["points"][0]["reps"] == 12  # tie on 50 kg -> most reps


async def test_progress_bodyweight_uses_reps(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_session(session, "crunches", date(2026, 5, 18), [(None, "20")])
    await _seed_session(session, "crunches", date(2026, 5, 25), [(None, "25"), (None, "15")])
    body = (await auth_client.get("/api/v1/exercises/crunches/progress")).json()
    assert body["metric"] == "reps"
    assert [(p["date"], p["reps"]) for p in body["points"]] == [
        ("2026-05-18", 20),
        ("2026-05-25", 25),
    ]


async def test_progress_unknown_exercise_404(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/api/v1/exercises/nope/progress")).status_code == 404
