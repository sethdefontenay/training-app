"""Schemas for the plan-ingestion agent: the proposed (review-gated) plan."""

from datetime import date

from pydantic import BaseModel


class ProposedIngredient(BaseModel):
    name: str
    quantity: float | None = None
    unit: str | None = None


class ProposedMeal(BaseModel):
    meal_number: int
    slot: str
    name: str
    calories: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None
    ingredients: list[ProposedIngredient] = []


class ProposedPrescription(BaseModel):
    exercise_slug: str
    exercise_name: str
    is_bodyweight: bool = False
    sets_x_reps: str
    prescribed_weight: str | None = None
    order: int = 0


class ProposedTrainingDay(BaseModel):
    label: str
    weekday: str | None = None
    order: int = 0
    prescriptions: list[ProposedPrescription] = []


class ProposedPlan(BaseModel):
    source: str | None = None
    phase: int | None = None
    guidance: str | None = None
    steps_target: int | None = None
    water_min_l: float | None = None
    water_max_l: float | None = None
    electrolytes_per_day: int | None = None
    daily_calories: int | None = None
    daily_protein_g: int | None = None
    daily_carbs_g: int | None = None
    daily_fat_g: int | None = None
    training_days: list[ProposedTrainingDay] = []
    meals: list[ProposedMeal] = []
    # Fields the agent could not read confidently — flagged for review, never guessed.
    flagged_fields: list[str] = []


class IngestRequest(BaseModel):
    email_text: str
    attachments: list[str] = []  # extracted text of .docx attachments


class CommitRequest(BaseModel):
    start_date: date
    plan: ProposedPlan
