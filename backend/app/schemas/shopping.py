"""Shopping list schemas."""

from datetime import date

from pydantic import BaseModel


class ShoppingItemOut(BaseModel):
    id: int
    name: str
    quantity: float | None
    unit: str | None
    checked: bool


class ShoppingListOut(BaseModel):
    id: int
    week_start: date
    items: list[ShoppingItemOut]


class CheckItem(BaseModel):
    checked: bool
