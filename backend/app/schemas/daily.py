"""Daily task list schemas."""

from datetime import date

from pydantic import BaseModel, Field


class WellbeingIn(BaseModel):
    energy: int | None = Field(default=None, ge=1, le=10)
    motivation: int | None = Field(default=None, ge=1, le=10)
    stress: int | None = Field(default=None, ge=1, le=10)
    hunger: int | None = Field(default=None, ge=1, le=10)


class DailyLogIn(BaseModel):
    water_units: int | None = None
    electrolytes_done: bool | None = None
    notes: str | None = None


class ExerciseLine(BaseModel):
    slug: str
    name: str
    sets_x_reps: str
    prescribed_weight: str | None
    target_sets: int | None
    completed_sets: int
    # Heaviest weight from the most recent prior session ("N kg" / "BW" / "—" no history).
    last_week: str = "—"


class WorkoutBlock(BaseModel):
    label: str
    exercises: list[ExerciseLine]


class MobilityItem(BaseModel):
    slug: str
    name: str
    done: bool


class MealLine(BaseModel):
    id: int
    meal_number: int
    slot: str
    name: str
    carbs_g: int | None
    calories: int | None
    protein_g: int | None
    fat_g: int | None
    eaten: bool


class DailyView(BaseModel):
    date: date
    weekday: str
    has_plan: bool
    workout: WorkoutBlock | None
    mobility: list[MobilityItem] | None
    meals: list[MealLine]
    daily_carbs_total: int | None
    targets: dict[str, float | int | None]
    steps: dict[str, int | None]
    wellbeing: WellbeingIn
    water_units: int
    electrolytes_done: bool
    notes: str | None
