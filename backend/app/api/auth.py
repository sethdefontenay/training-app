"""Authentication routes (single user, email + password, JWT)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.security import create_access_token, verify_password
from app.services.invites import EmailTaken, redeem_invite

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep) -> TokenResponse:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, session: SessionDep) -> TokenResponse:
    """Invite-only signup: consume a single-use code to create a standard account."""
    try:
        user = await redeem_invite(session, body.code, body.email, body.password)
    except EmailTaken as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        ) from e
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or already-used invite code"
        )
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get("/me")
async def me(user: CurrentUser) -> dict[str, str | int | bool]:
    return {
        "id": user.id,
        "email": user.email,
        "is_admin": user.is_admin,
        "has_diabetes": user.has_diabetes,
        "has_health_integrations": user.has_health_integrations,
        "has_checkins": user.has_checkins,
        "timezone": user.timezone,
    }
