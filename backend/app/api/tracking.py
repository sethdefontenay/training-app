"""Measurements, mobility, and exercise-progression endpoints."""

from datetime import date

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import Exercise, Measurement, MobilityDone
from app.schemas.tracking import _MEASUREMENT_FIELDS as FIELDS
from app.schemas.tracking import (
    MeasurementIn,
    MeasurementOut,
    MeasurementWithChange,
    MobilityDoneIn,
    ProgressionPoint,
)
from app.services.workouts import get_or_create_exercise, progression

router = APIRouter(tags=["tracking"])


def _to_out(row: Measurement) -> MeasurementOut:
    return MeasurementOut(date=row.date, **{f: getattr(row, f) for f in FIELDS})


@router.post("/measurements", response_model=MeasurementOut)
async def upsert_measurement(
    body: MeasurementIn, session: SessionDep, user: CurrentUser
) -> MeasurementOut:
    row = await session.scalar(select(Measurement).where(Measurement.date == body.date))
    if row is None:
        row = Measurement(date=body.date)
        session.add(row)
    for field in FIELDS:
        value = getattr(body, field)
        if value is not None:
            setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return _to_out(row)


@router.get("/measurements", response_model=list[MeasurementOut])
async def list_measurements(session: SessionDep, user: CurrentUser) -> list[MeasurementOut]:
    rows = (await session.execute(select(Measurement).order_by(Measurement.date))).scalars().all()
    return [_to_out(r) for r in rows]


@router.get("/measurements/{on}", response_model=MeasurementWithChange)
async def measurement_with_change(
    on: date, session: SessionDep, user: CurrentUser
) -> MeasurementWithChange:
    row = await session.scalar(select(Measurement).where(Measurement.date == on))
    if row is None:
        return MeasurementWithChange(date=on)
    prev = await session.scalar(
        select(Measurement).where(Measurement.date < on).order_by(Measurement.date.desc()).limit(1)
    )
    changes: dict[str, float] = {}
    if prev is not None:
        for field in FIELDS:
            cur, old = getattr(row, field), getattr(prev, field)
            if cur is not None and old is not None:
                changes[field] = round(cur - old, 2)
    return MeasurementWithChange(
        date=row.date, changes=changes, **{f: getattr(row, f) for f in FIELDS}
    )


@router.post("/mobility/done", status_code=status.HTTP_201_CREATED)
async def mark_mobility_done(
    body: MobilityDoneIn, session: SessionDep, user: CurrentUser
) -> dict[str, bool]:
    ex = await get_or_create_exercise(session, body.exercise_slug)
    existing = await session.scalar(
        select(MobilityDone).where(
            MobilityDone.date == body.date, MobilityDone.exercise_id == ex.id
        )
    )
    if existing is None:
        session.add(MobilityDone(date=body.date, exercise_id=ex.id))
        await session.commit()
    return {"done": True}


@router.delete("/mobility/done", status_code=status.HTTP_200_OK)
async def unmark_mobility_done(
    on: date, exercise_slug: str, session: SessionDep, user: CurrentUser
) -> dict[str, bool]:
    ex = await session.scalar(select(Exercise).where(Exercise.slug == exercise_slug))
    if ex is not None:
        existing = await session.scalar(
            select(MobilityDone).where(MobilityDone.date == on, MobilityDone.exercise_id == ex.id)
        )
        if existing is not None:
            await session.delete(existing)
            await session.commit()
    return {"done": False}


@router.get("/mobility/done", response_model=list[str])
async def list_mobility_done(on: date, session: SessionDep, user: CurrentUser) -> list[str]:
    rows = (
        (
            await session.execute(
                select(Exercise.slug)
                .join(MobilityDone, MobilityDone.exercise_id == Exercise.id)
                .where(MobilityDone.date == on)
                .order_by(Exercise.slug)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


@router.get("/exercises/{slug}/progression", response_model=list[ProgressionPoint])
async def exercise_progression(
    slug: str, session: SessionDep, user: CurrentUser
) -> list[ProgressionPoint]:
    points = await progression(session, slug)
    return [ProgressionPoint(date=p["date"], display=str(p["display"])) for p in points]
