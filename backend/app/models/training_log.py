"""Logged training data: sessions, sets, mobility completions, meal adherence."""

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.plan import Exercise


class Session(Base, TimestampMixin):
    __tablename__ = "session"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    weekday: Mapped[str | None] = mapped_column(default=None)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("plan.id"), default=None)
    training_day_id: Mapped[int | None] = mapped_column(ForeignKey("training_day.id"), default=None)
    # Session notes (vault: bodyweight/energy/shoulder/how-it-felt/what-to-change/cardio).
    bodyweight_kg: Mapped[float | None] = mapped_column(default=None)
    pre_energy: Mapped[int | None] = mapped_column(default=None)
    shoulder_check: Mapped[str | None] = mapped_column(Text, default=None)
    how_it_felt: Mapped[str | None] = mapped_column(Text, default=None)
    what_to_change: Mapped[str | None] = mapped_column(Text, default=None)
    post_cardio_done: Mapped[bool] = mapped_column(default=False)

    sets: Mapped[list["SetEntry"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class SetEntry(Base, TimestampMixin):
    __tablename__ = "set_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("session.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"), index=True)
    set_index: Mapped[int]  # 1-indexed
    # Strings to match the vault; empty/None weight = bodyweight.
    reps: Mapped[str | None] = mapped_column(default=None)
    weight: Mapped[str | None] = mapped_column(default=None)

    session: Mapped[Session] = relationship(back_populates="sets")
    exercise: Mapped["Exercise"] = relationship()


class MobilityDone(Base, TimestampMixin):
    __tablename__ = "mobility_done"
    __table_args__ = (UniqueConstraint("date", "exercise_id", name="uq_mobility_done_day_ex"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"), index=True)


class MealCheck(Base, TimestampMixin):
    """Adherence only: 'I ate the planned meal' — no intake macros captured here."""

    __tablename__ = "meal_check"
    __table_args__ = (UniqueConstraint("date", "meal_id", name="uq_meal_check_day_meal"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id", ondelete="CASCADE"), index=True)
    eaten: Mapped[bool] = mapped_column(default=True)
    # tz-aware, matching every other timestamp in the schema (created_at,
    # glucose/insulin ts). asyncpg rejects a tz-aware value into a naive column.
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
