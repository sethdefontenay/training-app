"""All ORM models. Importing this package registers every table on Base.metadata."""

from app.models.base import Base
from app.models.checkin import CheckIn, CheckInPhoto
from app.models.health import GlucoseReading, InsulinEvent, SleepNight, StepsDay
from app.models.integration import IntegrationSetting
from app.models.plan import (
    Exercise,
    Meal,
    MealIngredient,
    Plan,
    Prescription,
    TrainingDay,
    WeekdaySchedule,
)
from app.models.shopping import ShoppingItem, ShoppingList
from app.models.training_log import MealCheck, MobilityDone, Session, SetEntry
from app.models.user import User
from app.models.wellbeing import DailyLog, DailyWellbeing, Measurement

__all__ = [
    "Base",
    "CheckIn",
    "CheckInPhoto",
    "DailyLog",
    "DailyWellbeing",
    "Exercise",
    "GlucoseReading",
    "InsulinEvent",
    "IntegrationSetting",
    "Meal",
    "MealCheck",
    "MealIngredient",
    "Measurement",
    "MobilityDone",
    "Plan",
    "Prescription",
    "ShoppingItem",
    "ShoppingList",
    "SleepNight",
    "Session",
    "SetEntry",
    "StepsDay",
    "TrainingDay",
    "User",
    "WeekdaySchedule",
]
