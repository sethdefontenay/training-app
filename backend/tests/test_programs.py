"""Workout planner: program CRUD, exercises, weekday schedule, the day-view
override-with-fallback, import-from-plan, and cross-user isolation."""

from datetime import date

from httpx import AsyncClient

from app.models import MobilityDone, Prescription, ProgramExercise, SetEntry

DAY = "2026-06-01"


def test_exercise_fks_cascade_on_delete() -> None:
    """Every FK to exercise.id from a user-owned table must cascade, so deleting a user
    (which cascade-deletes their custom exercises) isn't blocked by a referencing row.
    Enforced at the Postgres layer; this guards the model definitions from regressing."""
    for model in (Prescription, SetEntry, MobilityDone, ProgramExercise):
        fk = next(iter(model.__table__.c.exercise_id.foreign_keys))
        assert fk.ondelete == "CASCADE", f"{model.__name__}.exercise_id must be ON DELETE CASCADE"


WEEKDAY = date.fromisoformat(DAY).strftime("%A").lower()


async def _create_program(client: AsyncClient, name: str = "Push Day") -> int:
    r = await client.post("/api/v1/programs", json={"name": name})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def test_program_crud(auth_client: AsyncClient) -> None:
    pid = await _create_program(auth_client)
    assert any(p["id"] == pid for p in (await auth_client.get("/api/v1/programs")).json())
    renamed = await auth_client.patch(f"/api/v1/programs/{pid}", json={"name": "Pull Day"})
    assert renamed.json()["name"] == "Pull Day"
    assert (await auth_client.delete(f"/api/v1/programs/{pid}")).status_code == 204
    assert (await auth_client.get("/api/v1/programs")).json() == []


async def test_add_edit_remove_exercise(auth_client: AsyncClient) -> None:
    pid = await _create_program(auth_client)
    added = await auth_client.post(
        f"/api/v1/programs/{pid}/exercises",
        json={"exercise_slug": "bench-press", "sets_x_reps": "4 × 8", "prescribed_weight": "60"},
    )
    assert added.status_code == 201
    pe = added.json()["exercises"][0]
    assert pe["exercise_slug"] == "bench-press" and pe["prescribed_weight"] == "60"
    edited = await auth_client.patch(
        f"/api/v1/programs/{pid}/exercises/{pe['id']}", json={"sets_x_reps": "5 × 5"}
    )
    assert edited.json()["exercises"][0]["sets_x_reps"] == "5 × 5"
    assert (
        await auth_client.delete(f"/api/v1/programs/{pid}/exercises/{pe['id']}")
    ).status_code == 204
    assert (await auth_client.get("/api/v1/programs")).json()[0]["exercises"] == []


async def test_schedule_assign_and_clear(auth_client: AsyncClient) -> None:
    pid = await _create_program(auth_client)
    r = await auth_client.put(f"/api/v1/programs/schedule/{WEEKDAY}", json={"program_id": pid})
    assert r.status_code == 200 and r.json()["program_id"] == pid
    sched = (await auth_client.get("/api/v1/programs/schedule")).json()
    assert any(s["weekday"] == WEEKDAY and s["program_id"] == pid for s in sched)
    await auth_client.put(f"/api/v1/programs/schedule/{WEEKDAY}", json={"program_id": None})
    assert (await auth_client.get("/api/v1/programs/schedule")).json() == []


async def test_assign_invalid_weekday_rejected(auth_client: AsyncClient) -> None:
    pid = await _create_program(auth_client)
    assert (
        await auth_client.put("/api/v1/programs/schedule/funday", json={"program_id": pid})
    ).status_code == 400


async def test_planner_drives_today(auth_client: AsyncClient) -> None:
    pid = await _create_program(auth_client, "Leg Day")
    await auth_client.post(
        f"/api/v1/programs/{pid}/exercises",
        json={"exercise_slug": "hack-squat", "sets_x_reps": "4 × 10"},
    )
    await auth_client.put(f"/api/v1/programs/schedule/{WEEKDAY}", json={"program_id": pid})
    view = (await auth_client.get(f"/api/v1/daily/{DAY}")).json()
    assert view["workout"]["label"] == "Leg Day"
    assert "hack-squat" in [e["slug"] for e in view["workout"]["exercises"]]
    assert view["workout"]["exercises"][0]["target_sets"] == 4


async def test_planner_overrides_pt_plan_and_reverts_on_delete(
    auth_client: AsyncClient, session
) -> None:
    from tests.test_daily import TRAIN, _seed_plan

    await _seed_plan(session)
    train_weekday = TRAIN.strftime("%A").lower()
    train_day = TRAIN.isoformat()
    # Baseline: no planner assignment -> PT plan drives the day.
    assert (await auth_client.get(f"/api/v1/daily/{train_day}")).json()["workout"][
        "label"
    ] == "Training Day 1"
    # Assign a planner program to that weekday -> it overrides the PT plan.
    pid = await _create_program(auth_client, "My Override")
    await auth_client.post(
        f"/api/v1/programs/{pid}/exercises",
        json={"exercise_slug": "custom-move", "sets_x_reps": "3 × 12"},
    )
    await auth_client.put(f"/api/v1/programs/schedule/{train_weekday}", json={"program_id": pid})
    assert (await auth_client.get(f"/api/v1/daily/{train_day}")).json()["workout"][
        "label"
    ] == "My Override"
    # Delete the program -> assignment gone -> reverts to the PT fallback.
    await auth_client.delete(f"/api/v1/programs/{pid}")
    assert (await auth_client.get(f"/api/v1/daily/{train_day}")).json()["workout"][
        "label"
    ] == "Training Day 1"


async def test_import_creates_and_preassigns(auth_client: AsyncClient, session) -> None:
    from tests.test_daily import TRAIN, _seed_plan

    await _seed_plan(session)
    counts = (await auth_client.post("/api/v1/programs/import-training-days")).json()
    assert counts["created"] >= 1 and counts["assigned"] >= 1
    progs = (await auth_client.get("/api/v1/programs")).json()
    assert any(p["name"] == "Training Day 1" for p in progs)
    # The imported day is now planner-driven for its weekday.
    view = (await auth_client.get(f"/api/v1/daily/{TRAIN.isoformat()}")).json()
    assert view["workout"]["label"] == "Training Day 1"
    # Re-running skips duplicates by name.
    again = (await auth_client.post("/api/v1/programs/import-training-days")).json()
    assert again["created"] == 0 and again["skipped"] >= 1


async def test_import_no_plan_returns_zeros(auth_client: AsyncClient) -> None:
    assert (await auth_client.post("/api/v1/programs/import-training-days")).json() == {
        "created": 0,
        "skipped": 0,
        "assigned": 0,
    }


async def test_program_isolation(auth_client: AsyncClient, other_client: AsyncClient) -> None:
    pid = await _create_program(auth_client, "A's program")
    # B sees none of A's programs and cannot mutate or schedule them.
    assert (await other_client.get("/api/v1/programs")).json() == []
    assert (
        await other_client.patch(f"/api/v1/programs/{pid}", json={"name": "x"})
    ).status_code == 404
    assert (await other_client.delete(f"/api/v1/programs/{pid}")).status_code == 404
    assert (
        await other_client.post(
            f"/api/v1/programs/{pid}/exercises", json={"exercise_slug": "x", "sets_x_reps": "1"}
        )
    ).status_code == 404
    assert (
        await other_client.put("/api/v1/programs/schedule/monday", json={"program_id": pid})
    ).status_code == 404
