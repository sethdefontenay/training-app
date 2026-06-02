"""Plan endpoints: AI ingest (propose), review-gated commit, list/current."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.integrations.health import IntegrationNotConfigured
from app.integrations.ingest import (
    ClaudeIngestionAgent,
    GmailClient,
    GmailProvider,
    IngestionAgent,
)
from app.models import Plan
from app.schemas.plan_ingest import CommitRequest, IngestRequest, ProposedPlan
from app.services.plan_commit import commit_plan

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
    plan = await commit_plan(session, body.plan, body.start_date)
    return {"plan_id": plan.id}


@router.get("")
async def list_plans(session: SessionDep, user: CurrentUser) -> list[dict[str, object]]:
    rows = (await session.execute(select(Plan).order_by(Plan.start_date.desc()))).scalars().all()
    return [
        {
            "id": p.id,
            "start_date": p.start_date.isoformat(),
            "is_current": p.is_current,
            "source": p.source,
        }
        for p in rows
    ]
