"""Declarative base + shared mixins."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class OwnedMixin:
    """Adds the required owner FK to a root domain table.

    Every root (non-child) domain table is scoped to the user who owns it. Child
    tables (e.g. set_entry, meal, prescription) inherit ownership through their
    parent FK and do not carry user_id directly. SQLAlchemy 2.0 copies this column
    onto each subclass, so a single declaration keeps the FK definition uniform.
    """

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
