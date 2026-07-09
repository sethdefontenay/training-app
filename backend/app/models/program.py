"""User-owned workout planner: programs the user builds themselves and a per-user
weekday→program schedule. Decoupled from the PT plan (Plan/TrainingDay/WeekdaySchedule):
the planner is the user's own, and drives the daily view when a weekday is assigned,
falling back to the PT plan otherwise.
"""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OwnedMixin, TimestampMixin


class WorkoutProgram(OwnedMixin, Base, TimestampMixin):
    """A named, user-owned workout program (a reusable list of exercises)."""

    __tablename__ = "workout_program"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    exercises: Mapped[list["ProgramExercise"]] = relationship(
        back_populates="program", cascade="all, delete-orphan", order_by="ProgramExercise.order"
    )


class ProgramExercise(Base, TimestampMixin):
    """An exercise within a program, with its target (mirrors Prescription's fields).

    Child of WorkoutProgram — ownership is inherited through the program. Reuses the
    shared/custom Exercise catalog via exercise_id.
    """

    __tablename__ = "program_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("workout_program.id", ondelete="CASCADE"), index=True
    )
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"), index=True)
    sets_x_reps: Mapped[str]
    prescribed_weight: Mapped[str | None] = mapped_column(default=None)  # kg string; empty = BW
    order: Mapped[int] = mapped_column(default=0)

    program: Mapped[WorkoutProgram] = relationship(back_populates="exercises")


class WeekdayProgram(OwnedMixin, Base, TimestampMixin):
    """Assigns one of the user's programs to a weekday. At most one program per weekday
    per user; deleting the program cascade-clears the assignment (weekday reverts to the
    PT-plan fallback)."""

    __tablename__ = "weekday_program"
    __table_args__ = (UniqueConstraint("user_id", "weekday", name="uq_weekday_program_user_day"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[str]  # "monday".."sunday"
    program_id: Mapped[int] = mapped_column(
        ForeignKey("workout_program.id", ondelete="CASCADE"), index=True
    )
