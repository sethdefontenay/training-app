"""Weekly shopping list, generated from the active plan's meals; items checkable."""

from datetime import date

from sqlalchemy import Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OwnedMixin, TimestampMixin


class ShoppingList(OwnedMixin, Base, TimestampMixin):
    __tablename__ = "shopping_list"

    id: Mapped[int] = mapped_column(primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plan.id", ondelete="CASCADE"), index=True)
    week_start: Mapped[date] = mapped_column(Date)

    items: Mapped[list["ShoppingItem"]] = relationship(
        back_populates="shopping_list", cascade="all, delete-orphan"
    )


class ShoppingItem(Base, TimestampMixin):
    __tablename__ = "shopping_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    shopping_list_id: Mapped[int] = mapped_column(
        ForeignKey("shopping_list.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    quantity: Mapped[float | None] = mapped_column(default=None)
    unit: Mapped[str | None] = mapped_column(default=None)
    checked: Mapped[bool] = mapped_column(default=False)

    shopping_list: Mapped[ShoppingList] = relationship(back_populates="items")
