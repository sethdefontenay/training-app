"""Synced health data: steps, sleep (google-health) and diabetes (Tidepool)."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class StepsDay(Base, TimestampMixin):
    __tablename__ = "steps_day"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    steps: Mapped[int] = mapped_column(default=0)
    target_steps: Mapped[int | None] = mapped_column(default=None)
    target_met: Mapped[bool] = mapped_column(default=False)
    source: Mapped[str] = mapped_column(default="google-health")
    manual: Mapped[bool] = mapped_column(default=False)  # set when user overrides
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class SleepNight(Base, TimestampMixin):
    __tablename__ = "sleep_night"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, unique=True, index=True)
    bedtime: Mapped[str | None] = mapped_column(default=None)  # HH:MM
    wake_time: Mapped[str | None] = mapped_column(default=None)
    asleep_min: Mapped[float | None] = mapped_column(default=None)
    in_bed_min: Mapped[float | None] = mapped_column(default=None)
    awake_min: Mapped[float | None] = mapped_column(default=None)
    light_min: Mapped[float | None] = mapped_column(default=None)
    deep_min: Mapped[float | None] = mapped_column(default=None)
    rem_min: Mapped[float | None] = mapped_column(default=None)
    efficiency: Mapped[float | None] = mapped_column(default=None)
    sessions: Mapped[int | None] = mapped_column(default=None)
    device: Mapped[str | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(default="google-health")
    manual: Mapped[bool] = mapped_column(default=False)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class GlucoseReading(Base, TimestampMixin):
    """Dexcom CGM reading, pulled via Tidepool. Seth's own record (not in PT package)."""

    __tablename__ = "glucose_reading"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    mmol_l: Mapped[float]
    source: Mapped[str] = mapped_column(default="tidepool")


class InsulinEvent(Base, TimestampMixin):
    """Tandem pump event (basal/bolus), pulled via Tidepool after a manual uploader run."""

    __tablename__ = "insulin_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    kind: Mapped[str]  # "bolus" | "basal"
    units: Mapped[float]
    carbs_g: Mapped[float | None] = mapped_column(default=None)
    source: Mapped[str] = mapped_column(default="tidepool")
