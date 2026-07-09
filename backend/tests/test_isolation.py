"""Cross-user data isolation: two independent owners never see each other's data.

`auth_client` is user A (the owner); `other_client` is user B (a separate account). These
exercise the universal surface (workouts, measurements, daily) that both users can reach,
and assert strict per-user separation on reads, writes, and by-id fetches.
"""

from httpx import AsyncClient

DAY = "2026-05-25"


async def test_sessions_are_isolated(auth_client: AsyncClient, other_client: AsyncClient) -> None:
    a = await auth_client.post("/api/v1/sessions", json={"date": DAY})
    a_id = a.json()["id"]

    # B cannot see A's session in the list or by id.
    assert (await other_client.get("/api/v1/sessions")).json() == []
    assert (await other_client.get(f"/api/v1/sessions/{a_id}")).status_code == 404

    # B can create its own session on the same date (per-user, no collision), and A
    # still only sees its own.
    b = await other_client.post("/api/v1/sessions", json={"date": DAY})
    assert b.status_code == 201
    b_id = b.json()["id"]
    # A cannot see B's session by id either — separation is mutual.
    assert (await auth_client.get(f"/api/v1/sessions/{b_id}")).status_code == 404


async def test_set_edits_are_isolated(auth_client: AsyncClient, other_client: AsyncClient) -> None:
    a = await auth_client.post("/api/v1/sessions", json={"date": DAY})
    a_sid = a.json()["id"]
    created = await auth_client.post(
        f"/api/v1/sessions/{a_sid}/sets",
        json={"exercise_slug": "leg-press-machine", "reps": "15", "weight": "40"},
    )
    a_set_id = created.json()["id"]
    # B cannot log against A's session, nor edit/delete A's set.
    assert (
        await other_client.post(
            f"/api/v1/sessions/{a_sid}/sets",
            json={"exercise_slug": "leg-press-machine", "reps": "1", "weight": "1"},
        )
    ).status_code == 404
    assert (
        await other_client.patch(f"/api/v1/sets/{a_set_id}", json={"reps": "99"})
    ).status_code == 404
    assert (await other_client.delete(f"/api/v1/sets/{a_set_id}")).status_code == 404


async def test_measurements_are_isolated(
    auth_client: AsyncClient, other_client: AsyncClient
) -> None:
    await auth_client.post("/api/v1/measurements", json={"date": DAY, "waist_cm": 96})
    # B sees none of A's measurements.
    assert (await other_client.get("/api/v1/measurements")).json() == []
    # B records its own on the same date; each sees only their own value.
    await other_client.post("/api/v1/measurements", json={"date": DAY, "waist_cm": 80})
    assert (await auth_client.get(f"/api/v1/measurements/{DAY}")).json()["waist_cm"] == 96
    assert (await other_client.get(f"/api/v1/measurements/{DAY}")).json()["waist_cm"] == 80


async def test_daily_wellbeing_is_isolated(
    auth_client: AsyncClient, other_client: AsyncClient
) -> None:
    await auth_client.put(f"/api/v1/daily/{DAY}/wellbeing", json={"energy": 8})
    # B's day view for the same date shows no wellbeing from A.
    b_view = (await other_client.get(f"/api/v1/daily/{DAY}")).json()
    assert b_view["wellbeing"]["energy"] is None
    # A's own day view still reflects A's entry.
    a_view = (await auth_client.get(f"/api/v1/daily/{DAY}")).json()
    assert a_view["wellbeing"]["energy"] == 8
