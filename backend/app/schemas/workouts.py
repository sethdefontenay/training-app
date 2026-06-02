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
