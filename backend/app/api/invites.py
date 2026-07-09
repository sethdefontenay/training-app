"""Admin-only invite management: mint and list single-use registration codes."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, SessionDep
from app.models import Invite
from app.schemas.auth import InviteCreate, InviteOut
from app.services.invites import mint_invite

router = APIRouter(prefix="/invites", tags=["invites"])


def _to_out(inv: Invite) -> InviteOut:
    return InviteOut(
        id=inv.id,
        code=inv.code,
        email=inv.email,
        used=inv.used_at is not None,
        created_at=inv.created_at,
    )


@router.post("", response_model=InviteOut, status_code=201)
async def create_invite(body: InviteCreate, session: SessionDep, admin: AdminUser) -> InviteOut:
    inv = await mint_invite(session, admin.id, body.email)
    return _to_out(inv)


@router.get("", response_model=list[InviteOut])
async def list_invites(session: SessionDep, admin: AdminUser) -> list[InviteOut]:
    rows = (
        (await session.execute(select(Invite).order_by(Invite.created_at.desc()))).scalars().all()
    )
    return [_to_out(i) for i in rows]
