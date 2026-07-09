"""The PT-prescribed plan (a ~6-week block) and everything it contains.

A plan is the structured output of the ingestion agent: training days + exercises +
prescriptions, mobility, meals + macros, weekday schedule, and daily targets. Exactly one
plan is current at a time; old plans are archived (is_current=False) but kept.
"""

from datetime import date

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OwnedMixin, TimestampMixin


class Plan(OwnedMixin, Base, TimestampMixin):
    __tablename__ = "plan"
    # At most one current plan per user (partial unique index on the owner).
    __table_args__ = (
        Index(
            "uq_plan_current_per_user",
            "user_id",
            unique=True,
            sqlite_where=text("is_current"),
            postgresql_where=text("is_current"),
        ),
    )

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
    """Exercise catalog: a shared base (owner_id IS NULL, readable by everyone) plus
    per-user custom exercises (owner_id set). Slug uniqueness is split — globally
    unique among base rows, and unique per owner among custom rows — so a user's custom
    exercise may reuse a base slug without colliding. See U4 for the merged read path.
    """

    __tablename__ = "exercise"
    __table_args__ = (
        # Per-owner uniqueness for custom rows. NULL owner_ids are distinct under both
        # Postgres and SQLite, so this does NOT constrain base rows — the partial index
        # below enforces global-slug uniqueness for those.
        UniqueConstraint("owner_id", "slug", name="uq_exercise_owner_slug"),
        Index(
            "uq_exercise_global_slug",
            "slug",
            unique=True,
            sqlite_where=text("owner_id IS NULL"),
            postgresql_where=text("owner_id IS NULL"),
        ),
        Index("ix_exercise_slug", "slug"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # NULL = shared base catalog; set = a user's private custom exercise.
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), default=None, index=True
    )
    slug: Mapped[str]
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
    exercise_id: Mapped[int] = mapped_column(
        ForeignKey("exercise.id", ondelete="CASCADE"), index=True
    )
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
