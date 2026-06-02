"""Weekly shopping list endpoints."""

from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.models import ShoppingItem, ShoppingList
from app.schemas.shopping import CheckItem, ShoppingItemOut, ShoppingListOut
from app.services.shopping import current_plan, generate_for_plan

router = APIRouter(prefix="/shopping", tags=["shopping"])


def _to_out(sl: ShoppingList) -> ShoppingListOut:
    items = sorted(sl.items, key=lambda i: i.name)
    return ShoppingListOut(
        id=sl.id,
        week_start=sl.week_start,
        items=[
            ShoppingItemOut(
                id=i.id, name=i.name, quantity=i.quantity, unit=i.unit, checked=i.checked
            )
            for i in items
        ],
    )


def _week_start(today: date) -> date:
    return today - timedelta(days=today.weekday())


async def _latest_for_current_plan(session: SessionDep) -> ShoppingList | None:
    plan = await current_plan(session)
    if plan is None:
        return None
    result: ShoppingList | None = await session.scalar(
        select(ShoppingList)
        .where(ShoppingList.plan_id == plan.id)
        .order_by(ShoppingList.week_start.desc(), ShoppingList.id.desc())
        .options(selectinload(ShoppingList.items))
        .limit(1)
    )
    return result


@router.get("", response_model=ShoppingListOut)
async def get_shopping(session: SessionDep, user: CurrentUser) -> ShoppingListOut:
    sl = await _latest_for_current_plan(session)
    if sl is None:
        plan = await current_plan(session)
        if plan is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan")
        sl = await generate_for_plan(session, plan, _week_start(date.today()))
        sl = await session.scalar(
            select(ShoppingList)
            .where(ShoppingList.id == sl.id)
            .options(selectinload(ShoppingList.items))
        )
    assert sl is not None
    return _to_out(sl)


@router.patch("/items/{item_id}", response_model=ShoppingItemOut)
async def check_item(
    item_id: int, body: CheckItem, session: SessionDep, user: CurrentUser
) -> ShoppingItemOut:
    item = await session.get(ShoppingItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    item.checked = body.checked
    await session.commit()
    await session.refresh(item)
    return ShoppingItemOut(
        id=item.id, name=item.name, quantity=item.quantity, unit=item.unit, checked=item.checked
    )


@router.post("/regenerate", response_model=ShoppingListOut)
async def regenerate(session: SessionDep, user: CurrentUser) -> ShoppingListOut:
    plan = await current_plan(session)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active plan")
    created = await generate_for_plan(session, plan, _week_start(date.today()))
    reloaded: ShoppingList | None = await session.scalar(
        select(ShoppingList)
        .where(ShoppingList.id == created.id)
        .options(selectinload(ShoppingList.items))
    )
    assert reloaded is not None
    return _to_out(reloaded)
