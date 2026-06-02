"""The PT-prescribed plan (a ~6-week block) and everything it contains.

A plan is the structured output of the ingestion agent: training days + exercises +
prescriptions, mobility, meals + macros, weekday schedule, and daily targets. Exactly one
plan is current at a time; old plans are archived (is_current=False) but kept.
"""

from datetime import date

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Plan(Base, TimestampMixin):
    __tablename__ = "plan"

    id: Mapped[int] = mapped_column(primary_key=True)
    phase: Mapped[int | None] = mapped_column(default=None)
    source: Mapped[str | None] = mapped_column(default=None)  # e.g. "PT, 2026-05-21"
    start_date: Mapped[date]
    is_current: Mapped[bool] = mapped_column(default=False, index=True)
    guidance: Mapped[str | None] = mapped_column(Text, default=None)  # non-negotiables, etc.

    # Daily targets (from the plan overview / email prose).
    steps_target: Mapped[int | None] = mapped_column(default=None)
    water_min_l: Mapped[float | None] = mapped_column(default=None)
    water_max_l: Mapped[float | None] = mapped_column(default=None)
    electrolytes_per_day: Mapped[int | None] = mapped_column(default=None)
    daily_calories: Mapped[int | None] = mapped_column(default=None)
    daily_protein_g: Mapped[int | None] = mapped_column(default=None)
    daily_carbs_g: Mapped[int | None] = mapped_column(default=None)
    daily_fat_g: Mapped[int | None] = mapped_column(default=None)

    training_days: Mapped[list["TrainingDay"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )
    meals: Mapped[list["Meal"]] = relationship(back_populates="plan", cascade="all, delete-orphan")
    schedule: Mapped[list["WeekdaySchedule"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class Exercise(Base, TimestampMixin):
    """Global exercise catalog (resistance + mobility share this where useful)."""

    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str]
    is_bodyweight: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str | None] = mapped_column(Text, default=None)


class TrainingDay(Base, TimestampMixin):
    __tablename__ = "training_day"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    label: Mapped[str]  # "Training Day 1"
    order: Mapped[int] = mapped_column(default=0)

    plan: Mapped[Plan] = relationship(back_populates="training_days")
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="training_day", cascade="all, delete-orphan"
    )


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescription"

    id: Mapped[int] = mapped_column(primary_key=True)
    training_day_id: Mapped[int] = mapped_column(
        ForeignKey("training_day.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"), index=True)
    sets_x_reps: Mapped[str]  # vault stores as string, e.g. "4 × 15", "3 × 10 per leg"
    prescribed_weight: Mapped[str | None] = mapped_column(default=None)  # kg string; empty = BW
    order: Mapped[int] = mapped_column(default=0)
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    training_day: Mapped[TrainingDay] = relationship(back_populates="prescriptions")
    exercise: Mapped[Exercise] = relationship()


class WeekdaySchedule(Base, TimestampMixin):
    """Maps a weekday to a training day (or rest) + whether mobility is scheduled."""

    __tablename__ = "weekday_schedule"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    weekday: Mapped[str]  # "monday".."sunday"
    training_day_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_day.id", ondelete="SET NULL"), default=None
    )
    has_mobility: Mapped[bool] = mapped_column(default=False)

    plan: Mapped[Plan] = relationship(back_populates="schedule")
    training_day: Mapped[TrainingDay | None] = relationship()


class Meal(Base, TimestampMixin):
    __tablename__ = "meal"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    meal_number: Mapped[int]  # 1..4
    slot: Mapped[str]  # breakfast/lunch/snack/dinner
    name: Mapped[str]
    calories: Mapped[int | None] = mapped_column(default=None)
    protein_g: Mapped[int | None] = mapped_column(default=None)
    carbs_g: Mapped[int | None] = mapped_column(default=None)  # the insulin number
    fat_g: Mapped[int | None] = mapped_column(default=None)

    plan: Mapped[Plan] = relationship(back_populates="meals")
    ingredients: Mapped[list["MealIngredient"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan"
    )


class MealIngredient(Base, TimestampMixin):
    __tablename__ = "meal_ingredient"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meal.id", ondelete="CASCADE"), index=True)
    name: Mapped[str]
    quantity: Mapped[float | None] = mapped_column(default=None)
    unit: Mapped[str | None] = mapped_column(default=None)  # g, ml, "medium", etc.
    order: Mapped[int] = mapped_column(default=0)

    meal: Mapped[Meal] = relationship(back_populates="ingredients")
