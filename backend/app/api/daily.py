"""Daily task list endpoints: the day view, wellbeing, daily log, meal adherence."""

from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import DailyLog, DailyWellbeing, MealCheck
from app.schemas.daily import DailyLogIn, DailyView, WellbeingIn
from app.services.daily import resolve_day

router = APIRouter(prefix="/daily", tags=["daily"])


@router.get("/{day}", response_model=DailyView)
async def get_day(day: date, session: SessionDep, user: CurrentUser) -> DailyView:
    return await resolve_day(session, day)


@router.put("/{day}/wellbeing", response_model=WellbeingIn)
async def set_wellbeing(
    day: date, body: WellbeingIn, session: SessionDep, user: CurrentUser
) -> WellbeingIn:
    row = await session.scalar(select(DailyWellbeing).where(DailyWellbeing.date == day))
    if row is None:
        row = DailyWellbeing(date=day)
        session.add(row)
    for field in ("energy", "motivation", "stress", "hunger"):
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return WellbeingIn(
        energy=row.energy, motivation=row.motivation, stress=row.stress, hunger=row.hunger
    )


@router.put("/{day}/log", response_model=DailyLogIn)
async def set_log(
    day: date, body: DailyLogIn, session: SessionDep, user: CurrentUser
) -> DailyLogIn:
    row = await session.scalar(select(DailyLog).where(DailyLog.date == day))
    if row is None:
        row = DailyLog(date=day)
        session.add(row)
    if body.water_units is not None:
        row.water_units = body.water_units
    if body.electrolytes_done is not None:
        row.electrolytes_done = body.electrolytes_done
    if body.notes is not None:
        row.notes = body.notes
    await session.commit()
    await session.refresh(row)
    return DailyLogIn(
        water_units=row.water_units, electrolytes_done=row.electrolytes_done, notes=row.notes
    )


@router.post("/{day}/meals/{meal_id}/check", status_code=status.HTTP_200_OK)
async def check_meal(
    day: date, meal_id: int, session: SessionDep, user: CurrentUser
) -> dict[str, bool]:
    existing = await session.scalar(
        select(MealCheck).where(MealCheck.date == day, MealCheck.meal_id == meal_id)
    )
    if existing is None:
        session.add(MealCheck(date=day, meal_id=meal_id, eaten=True))
    else:
        existing.eaten = True
    await session.commit()
    return {"eaten": True}
