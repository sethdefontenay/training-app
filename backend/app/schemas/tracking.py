"""Measurements, mobility, and progression schemas."""

from datetime import date

from pydantic import BaseModel

_MEASUREMENT_FIELDS = (
    "waist_cm",
    "tummy_cm",
    "bum_cm",
    "right_thigh_cm",
    "left_thigh_cm",
    "weight_kg",
)


class MeasurementIn(BaseModel):
    date: date
    waist_cm: float | None = None
    tummy_cm: float | None = None
    bum_cm: float | None = None
    right_thigh_cm: float | None = None
    left_thigh_cm: float | None = None
    weight_kg: float | None = None


class MeasurementOut(MeasurementIn):
    pass


class MeasurementWithChange(MeasurementOut):
    changes: dict[str, float] = {}


class MobilityDoneIn(BaseModel):
    date: date
    exercise_slug: str


class ProgressionPoint(BaseModel):
    date: date
    display: str
