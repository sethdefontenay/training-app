"""Plan endpoints: AI ingest (propose), review-gated commit, list/current."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, owned
from app.clock import local_today
from app.integrations.health import IntegrationNotConfigured
from app.integrations.ingest import (
    ClaudeIngestionAgent,
    GmailClient,
    GmailProvider,
    IngestionAgent,
)
from app.models import (
    Exercise,
    Meal,
    MobilityDone,
    Plan,
    Prescription,
    TrainingDay,
    WeekdaySchedule,
)
from app.schemas.plan_ingest import CommitRequest, IngestRequest, ProposedPlan
from app.services.plan_commit import commit_plan

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

router = APIRouter(prefix="/plans", tags=["plans"])

_UNAVAILABLE = status.HTTP_503_SERVICE_UNAVAILABLE


def get_agent() -> IngestionAgent:
    return ClaudeIngestionAgent()


def get_gmail() -> GmailProvider:
    return GmailClient()


AgentDep = Annotated[IngestionAgent, Depends(get_agent)]
GmailDep = Annotated[GmailProvider, Depends(get_gmail)]


async def _extract(agent: IngestionAgent, text: str, attachments: list[str]) -> ProposedPlan:
    try:
        return await agent.extract(text, attachments)
    except IntegrationNotConfigured as e:
        raise HTTPException(status_code=_UNAVAILABLE, detail=str(e)) from e
    except NotImplementedError as e:
        raise HTTPException(
            status_code=_UNAVAILABLE, detail="Ingestion agent needs credentials"
        ) from e


@router.post("/ingest", response_model=ProposedPlan)
async def ingest(body: IngestRequest, user: CurrentUser, agent: AgentDep) -> ProposedPlan:
    # PROPOSE only — nothing is persisted here (human-in-the-loop commit is separate).
    return await _extract(agent, body.email_text, body.attachments)


@router.post("/ingest/gmail", response_model=ProposedPlan)
async def ingest_from_gmail(user: CurrentUser, agent: AgentDep, gmail: GmailDep) -> ProposedPlan:
    try:
        email = await gmail.fetch_latest_plan_email()
    except IntegrationNotConfigured as e:
        raise HTTPException(status_code=_UNAVAILABLE, detail=str(e)) from e
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No plan email found")
    return await _extract(agent, email.text, email.attachments)


@router.post("/commit", status_code=status.HTTP_201_CREATED)
async def commit(body: CommitRequest, session: SessionDep, user: CurrentUser) -> dict[str, int]:
    plan = await commit_plan(session, body.plan, body.start_date, user.id)
    return {"plan_id": plan.id}


@router.get("/current/detail")
async def current_detail(session: SessionDep, user: CurrentUser) -> dict[str, object]:
    """Aggregated view of the active plan: training days, meals, mobility, time since start."""
    plan = await session.scalar(
        owned(select(Plan), Plan, user)
        .where(Plan.is_current.is_(True))
        .options(
            selectinload(Plan.training_days)
            .selectinload(TrainingDay.prescriptions)
            .selectinload(Prescription.exercise),
            selectinload(Plan.meals).selectinload(Meal.ingredients),
            selectinload(Plan.schedule).selectinload(WeekdaySchedule.training_day),
        )
    )
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan")

    schedule = {
        ws.weekday: (ws.training_day.label if ws.training_day else None, ws.has_mobility)
        for ws in plan.schedule
    }
    training_days = [
        {
            "label": td.label,
            "exercises": [
                {
                    "slug": p.exercise.slug,
                    "name": p.exercise.name,
                    "sets_x_reps": p.sets_x_reps,
                    "prescribed_weight": p.prescribed_weight,
                }
                for p in sorted(td.prescriptions, key=lambda x: x.order)
            ],
        }
        for td in sorted(plan.training_days, key=lambda x: x.order)
    ]
    meals = [
        {
            "meal_number": m.meal_number,
            "slot": m.slot,
            "name": m.name,
            "calories": m.calories,
            "protein_g": m.protein_g,
            "carbs_g": m.carbs_g,
            "fat_g": m.fat_g,
            "ingredients": [
                {"name": i.name, "quantity": i.quantity, "unit": i.unit}
                for i in sorted(m.ingredients, key=lambda x: x.order)
            ],
        }
        for m in sorted(plan.meals, key=lambda x: x.meal_number)
    ]
    mobility = (
        (
            await session.execute(
                select(Exercise.name)
                .join(MobilityDone, MobilityDone.exercise_id == Exercise.id)
                .where(MobilityDone.user_id == user.id)
                .distinct()
                .order_by(Exercise.name)
            )
        )
        .scalars()
        .all()
    )
    return {
        "source": plan.source,
        "phase": plan.phase,
        "start_date": plan.start_date.isoformat(),
        "days_since_start": (local_today() - plan.start_date).days,
        "targets": {
            "steps_target": plan.steps_target,
            "water_min_l": plan.water_min_l,
            "water_max_l": plan.water_max_l,
            "electrolytes_per_day": plan.electrolytes_per_day,
            "daily_calories": plan.daily_calories,
            "daily_protein_g": plan.daily_protein_g,
            "daily_carbs_g": plan.daily_carbs_g,
            "daily_fat_g": plan.daily_fat_g,
        },
        "schedule": {wd: schedule.get(wd, (None, False)) for wd in _WEEKDAYS},
        "training_days": training_days,
        "meals": meals,
        "mobility": list(mobility),
    }


@router.get("")
async def list_plans(session: SessionDep, user: CurrentUser) -> list[dict[str, object]]:
    rows = (
        (await session.execute(owned(select(Plan), Plan, user).order_by(Plan.start_date.desc())))
        .scalars()
        .all()
    )
    return [
        {
            "id": p.id,
            "start_date": p.start_date.isoformat(),
            "is_current": p.is_current,
            "source": p.source,
        }
        for p in rows
    ]
