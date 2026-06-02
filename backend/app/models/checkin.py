"""Weekly PT check-in (rolling 7-day window) + attached posed photos."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class CheckIn(Base, TimestampMixin):
    __tablename__ = "check_in"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_on: Mapped[date] = mapped_column(Date, index=True)
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    worked_on: Mapped[str | None] = mapped_column(Text, default=None)
    struggles: Mapped[str | None] = mapped_column(Text, default=None)
    completed: Mapped[bool] = mapped_column(default=False)

    photos: Mapped[list["CheckInPhoto"]] = relationship(
        back_populates="check_in", cascade="all, delete-orphan"
    )


class CheckInPhoto(Base, TimestampMixin):
    __tablename__ = "check_in_photo"

    id: Mapped[int] = mapped_column(primary_key=True)
    check_in_id: Mapped[int] = mapped_column(
        ForeignKey("check_in.id", ondelete="CASCADE"), index=True
    )
    storage_path: Mapped[str]
    content_type: Mapped[str | None] = mapped_column(default=None)

    check_in: Mapped[CheckIn] = relationship(back_populates="photos")
