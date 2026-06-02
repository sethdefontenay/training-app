"""Weekly check-in schemas."""

from datetime import date

from pydantic import BaseModel

from app.schemas.tracking import MeasurementOut


class CheckInStart(BaseModel):
    started_on: date | None = None


class Reflections(BaseModel):
    worked_on: str | None = None
    struggles: str | None = None


class PhotoOut(BaseModel):
    id: int
    storage_path: str
    content_type: str | None


class CheckInView(BaseModel):
    id: int
    started_on: date
    window_start: date
    window_end: date
    measurements: MeasurementOut | None
    metrics: dict[str, dict[str, object]]
    sessions_logged: int
    worked_on: str | None
    struggles: str | None
    completed: bool
    photos: list[PhotoOut]


class CheckInSummary(BaseModel):
    id: int
    started_on: date
    window_start: date
    window_end: date
    completed: bool
