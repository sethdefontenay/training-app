"""plan_ingestion.feature: review-gated ingest, commit + versioning, Gmail, shopping."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.plans import get_agent, get_gmail
from app.integrations.ingest import PlanEmail
from app.main import app
from app.models import Plan, User
from app.schemas.plan_ingest import (
    ProposedIngredient,
    ProposedMeal,
    ProposedPlan,
    ProposedPrescription,
    ProposedTrainingDay,
)


def _sample() -> ProposedPlan:
    return ProposedPlan(
        source="PT, 2026-07-02",
        steps_target=7000,
        daily_carbs_g=212,
        training_days=[
            ProposedTrainingDay(
                label="Training Day 1",
                weekday="Monday",
                prescriptions=[
                    ProposedPrescription(
                        exercise_slug="leg-press-machine",
                        exercise_name="Leg Press Machine",
                        sets_x_reps="4 × 15",
                        prescribed_weight="10",
                    )
                ],
            )
        ],
        meals=[
            ProposedMeal(
                meal_number=1,
                slot="breakfast",
                name="Protein oats",
                carbs_g=74,
                ingredients=[ProposedIngredient(name="oats", quantity=80, unit="g")],
            )
        ],
        flagged_fields=["meal 2 carbs"],
    )


class FakeAgent:
    def __init__(self, proposal: ProposedPlan) -> None:
        self.proposal = proposal

    async def extract(self, email_text: str, attachments: list[str]) -> ProposedPlan:
        return self.proposal


class FakeGmail:
    def __init__(self, email: PlanEmail | None) -> None:
        self.email = email

    async def fetch_latest_plan_email(self) -> PlanEmail | None:
        return self.email


def _use_agent() -> None:
    app.dependency_overrides[get_agent] = lambda: FakeAgent(_sample())


async def test_ingest_proposes_without_committing(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    _use_agent()
    resp = await auth_client.post(
        "/api/v1/plans/ingest", json={"email_text": "hi", "attachments": ["docx text"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["training_days"][0]["label"] == "Training Day 1"
    assert "meal 2 carbs" in body["flagged_fields"]
    # nothing persisted — review-gated
    assert (await session.scalar(select(func.count()).select_from(Plan))) == 0


async def test_commit_creates_current_and_archives_old(
    auth_client: AsyncClient, session: AsyncSession
) -> None:
    uid = int(await session.scalar(select(User.id).order_by(User.id).limit(1)))
    session.add(Plan(user_id=uid, start_date=date(2026, 5, 21), is_current=True, source="old"))
    await session.commit()
    resp = await auth_client.post(
        "/api/v1/plans/commit",
        json={"start_date": "2026-07-02", "plan": _sample().model_dump()},
    )
    assert resp.status_code == 201
    listed = (await auth_client.get("/api/v1/plans")).json()
    assert len(listed) == 2  # old plan preserved (history)
    current = [p for p in listed if p["is_current"]]
    assert len(current) == 1
    assert current[0]["source"] == "PT, 2026-07-02"


async def test_commit_generates_shopping_list(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/plans/commit",
        json={"start_date": "2026-07-02", "plan": _sample().model_dump()},
    )
    shopping = (await auth_client.get("/api/v1/shopping")).json()
    oats = next(i for i in shopping["items"] if i["name"] == "oats")
    assert oats["quantity"] == 80 * 7


async def test_current_plan_detail(auth_client: AsyncClient) -> None:
    await auth_client.post(
        "/api/v1/plans/commit",
        json={"start_date": "2026-05-21", "plan": _sample().model_dump()},
    )
    d = (await auth_client.get("/api/v1/plans/current/detail")).json()
    assert d["source"] == "PT, 2026-07-02"
    assert isinstance(d["days_since_start"], int)
    assert d["days_since_start"] >= 0
    assert d["training_days"][0]["label"] == "Training Day 1"
    assert d["training_days"][0]["exercises"][0]["slug"] == "leg-press-machine"
    assert d["meals"][0]["carbs_g"] == 74
    ing = d["meals"][0]["ingredients"][0]
    assert ing["name"] == "oats"
    assert ing["quantity"] == 80
    assert ing["unit"] == "g"


async def test_ingest_unconfigured_503(auth_client: AsyncClient) -> None:
    app.dependency_overrides.pop(get_agent, None)
    resp = await auth_client.post("/api/v1/plans/ingest", json={"email_text": "x"})
    assert resp.status_code == 503


async def test_ingest_from_gmail(auth_client: AsyncClient) -> None:
    _use_agent()
    app.dependency_overrides[get_gmail] = lambda: FakeGmail(
        PlanEmail(text="hi", sender="pt", attachments=[])
    )
    resp = await auth_client.post("/api/v1/plans/ingest/gmail")
    assert resp.status_code == 200
    assert resp.json()["source"] == "PT, 2026-07-02"


async def test_ingest_from_gmail_none_is_404(auth_client: AsyncClient) -> None:
    _use_agent()
    app.dependency_overrides[get_gmail] = lambda: FakeGmail(None)
    resp = await auth_client.post("/api/v1/plans/ingest/gmail")
    assert resp.status_code == 404
