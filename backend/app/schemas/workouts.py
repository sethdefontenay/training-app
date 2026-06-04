"""Workout logging schemas."""

from datetime import date

from pydantic import BaseModel


class SessionCreate(BaseModel):
    date: date
    training_day_id: int | None = None


class SetCreate(BaseModel):
    exercise_slug: str
    reps: str | None = None
    weight: str | None = None
    set_index: int | None = None


class SetUpdate(BaseModel):
    reps: str | None = None
    weight: str | None = None


class SetRead(BaseModel):
    id: int
    exercise_slug: str
    set_index: int
    reps: str | None
    weight: str | None
    display: str


class SessionRead(BaseModel):
    id: int
    date: date
    sets: list[SetRead]


class LastWeek(BaseModel):
    display: str


class ProgressPoint(BaseModel):
    date: date
    weight: float | None  # heaviest weight that day (kg), None for bodyweight days
    reps: int | None  # reps at the heaviest set (or best reps on bodyweight days)
    display: str


class ExerciseProgress(BaseModel):
    slug: str
    name: str
    metric: str  # "weight" | "reps" — what the series should be plotted as
    points: list[ProgressPoint]


class ExerciseSets(BaseModel):
    slug: str
    name: str
    sets: list[str]  # display strings, e.g. "40 kg × 15"


class SessionSummary(BaseModel):
    id: int
    date: date
    weekday: str | None
    exercises: list[ExerciseSets]
