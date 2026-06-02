"""Daily wellbeing (/10s), daily adherence log, and body measurements."""

from datetime import date

from sqlalchemy import CheckConstraint, Date, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

_TEN = "BETWEEN 1 AND 10"


class DailyWellbeing(Base, TimestampMixin):
    """The four /10s, logged daily, summarised into the weekly check-in."""

    __tablename__ = "daily_wellbeing"
    __table_args__ = (
        CheckConstraint(f"energy IS NULL OR energy {_TEN}", name="ck_energy_1_10"),
        CheckConstraint(f"motivation IS NULL OR motivation {_TEN}", name="ck_motivation_1_10"),
        CheckConstraint(f"stress IS NULL OR stress {_TEN}", name="ck_stress_1_10"),
        CheckConstraint(f"hunger IS NULL OR hunger {_TEN}", name="ck_hunger_1_10"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    energy: Mapped[int | None] = mapped_column(default=None)
    motivation: Mapped[int | None] = mapped_column(default=None)
    stress: Mapped[int | None] = mapped_column(default=None)
    hunger: Mapped[int | None] = mapped_column(default=None)


class DailyLog(Base, TimestampMixin):
    """Non-meal daily adherence: water, electrolytes, off-plan notes."""

    __tablename__ = "daily_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    water_units: Mapped[int] = mapped_column(default=0)
    electrolytes_done: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, default=None)


class Measurement(Base, TimestampMixin):
    __tablename__ = "measurement"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    waist_cm: Mapped[float | None] = mapped_column(default=None)
    tummy_cm: Mapped[float | None] = mapped_column(default=None)
    bum_cm: Mapped[float | None] = mapped_column(default=None)
    right_thigh_cm: Mapped[float | None] = mapped_column(default=None)
    left_thigh_cm: Mapped[float | None] = mapped_column(default=None)
    weight_kg: Mapped[float | None] = mapped_column(default=None)
