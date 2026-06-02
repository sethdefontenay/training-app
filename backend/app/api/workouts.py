"""Workout logging endpoints: sessions, sets, and the last-week column."""

from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.models import Session, SetEntry
from app.schemas.workouts import (
    LastWeek,
    SessionCreate,
    SessionRead,
    SetCreate,
    SetRead,
    SetUpdate,
)
from app.services.workouts import get_or_create_exercise, last_week_display, set_display

router = APIRouter(tags=["workouts"])


def _to_set_read(entry: SetEntry, slug: str) -> SetRead:
    return SetRead(
        id=entry.id,
        exercise_slug=slug,
        set_index=entry.set_index,
        reps=entry.reps,
        weight=entry.weight,
        display=set_display(entry.weight, entry.reps),
    )


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate, session: SessionDep, user: CurrentUser
) -> SessionRead:
    s = Session(
        date=body.date,
        weekday=body.date.strftime("%A"),
        training_day_id=body.training_day_id,
    )
    session.add(s)
    await session.commit()
    await session.refresh(s)
    return SessionRead(id=s.id, date=s.date, sets=[])


@router.get("/sessions/{session_id}", response_model=SessionRead)
async def get_session_detail(
    session_id: int, session: SessionDep, user: CurrentUser
) -> SessionRead:
    s = await session.scalar(
        select(Session)
        .where(Session.id == session_id)
        .options(selectinload(Session.sets).selectinload(SetEntry.exercise))
    )
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    ordered = sorted(s.sets, key=lambda e: (e.exercise_id, e.set_index))
    return SessionRead(
        id=s.id, date=s.date, sets=[_to_set_read(e, e.exercise.slug) for e in ordered]
    )


@router.post(
    "/sessions/{session_id}/sets",
    response_model=SetRead,
    status_code=status.HTTP_201_CREATED,
)
async def log_set(
    session_id: int, body: SetCreate, session: SessionDep, user: CurrentUser
) -> SetRead:
    s = await session.get(Session, session_id)
    if s is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    ex = await get_or_create_exercise(session, body.exercise_slug)
    if body.set_index is not None:
        index = body.set_index
    else:
        count = await session.scalar(
            select(func.count())
            .select_from(SetEntry)
            .where(SetEntry.session_id == session_id, SetEntry.exercise_id == ex.id)
        )
        index = (count or 0) + 1
    entry = SetEntry(
        session_id=session_id,
        exercise_id=ex.id,
        set_index=index,
        reps=body.reps,
        weight=body.weight,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return _to_set_read(entry, ex.slug)


@router.patch("/sets/{set_id}", response_model=SetRead)
async def edit_set(set_id: int, body: SetUpdate, session: SessionDep, user: CurrentUser) -> SetRead:
    entry = await session.scalar(
        select(SetEntry).where(SetEntry.id == set_id).options(selectinload(SetEntry.exercise))
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")
    if body.reps is not None:
        entry.reps = body.reps
    if body.weight is not None:
        entry.weight = body.weight
    await session.commit()
    await session.refresh(entry)
    return _to_set_read(entry, entry.exercise.slug)


@router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_set(set_id: int, session: SessionDep, user: CurrentUser) -> None:
    entry = await session.get(SetEntry, set_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Set not found")
    await session.delete(entry)
    await session.commit()


@router.get("/exercises/{slug}/last-week", response_model=LastWeek)
async def last_week(slug: str, before: date, session: SessionDep, user: CurrentUser) -> LastWeek:
    return LastWeek(display=await last_week_display(session, slug, before))
