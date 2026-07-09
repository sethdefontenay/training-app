"""Auth request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    code: str


class InviteCreate(BaseModel):
    # Optionally bind the invite to a specific email (registrant's email must match).
    email: EmailStr | None = None


class InviteOut(BaseModel):
    id: int
    code: str
    email: str | None
    used: bool
    created_at: datetime | None
