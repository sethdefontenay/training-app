"""Single-use invite codes. Provisioning is invite-only — no public signup."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Invite(Base, TimestampMixin):
    """An admin-minted code that lets exactly one person register.

    An invite may optionally be bound to an email (the registrant's email must then
    match). It is single-use: `used_at` is stamped when redeemed and a used or missing
    code is rejected at registration.
    """

    __tablename__ = "invite"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, index=True)
    # Optional pre-binding: when set, the registrant's email must match this value.
    email: Mapped[str | None] = mapped_column(default=None)
    created_by: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
