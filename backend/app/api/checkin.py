"""Weekly PT check-in endpoints: start, assemble, reflections, photos, finish."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep, owned
from app.clock import local_today
from app.config import get_settings
from app.models import CheckIn, CheckInPhoto
from app.schemas.checkin import (
    CheckInStart,
    CheckInSummary,
    CheckInView,
    PhotoOut,
    Reflections,
)
from app.schemas.tracking import MeasurementOut
from app.services.checkin import (
    latest_measurement,
    latest_per_metric,
    metric_summaries,
    sessions_logged,
    sleep_summary,
    steps_average,
    window_for,
)

router = APIRouter(prefix="/check-ins", tags=["check-in"])

UPLOAD_DIR = Path(get_settings().upload_dir)
_FIELDS = ("waist_cm", "tummy_cm", "bum_cm", "right_thigh_cm", "left_thigh_cm", "weight_kg")


async def _assemble(session: SessionDep, ci: CheckIn) -> CheckInView:
    uid = ci.user_id
    measurement = await latest_measurement(session, ci.window_start, ci.window_end, uid)
    metrics = await metric_summaries(session, ci.window_start, ci.window_end, uid)
    logged = await sessions_logged(session, ci.window_start, ci.window_end, uid)
    latest = await latest_per_metric(session, ci.window_end, uid)
    steps_avg = await steps_average(session, ci.window_start, ci.window_end, uid)
    sleep = await sleep_summary(session, ci.window_start, ci.window_end, uid)
    m_out = (
        MeasurementOut(date=measurement.date, **{f: getattr(measurement, f) for f in _FIELDS})
        if measurement is not None
        else None
    )
    return CheckInView(
        id=ci.id,
        started_on=ci.started_on,
        window_start=ci.window_start,
        window_end=ci.window_end,
        measurements=m_out,
        latest_measurements=latest,
        metrics=metrics,
        steps_avg=steps_avg,
        sleep=sleep,
        sessions_logged=logged,
        worked_on=ci.worked_on,
        struggles=ci.struggles,
        completed=ci.completed,
        photos=[
            PhotoOut(id=p.id, storage_path=p.storage_path, content_type=p.content_type)
            for p in ci.photos
        ],
    )


async def _get(session: SessionDep, check_in_id: int, user: CurrentUser) -> CheckIn:
    ci = await session.scalar(
        owned(select(CheckIn), CheckIn, user)
        .where(CheckIn.id == check_in_id)
        .options(selectinload(CheckIn.photos))
    )
    if ci is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
    return ci


@router.post("", response_model=CheckInView, status_code=status.HTTP_201_CREATED)
async def start_check_in(body: CheckInStart, session: SessionDep, user: CurrentUser) -> CheckInView:
    started = body.started_on or local_today()
    win_start, win_end = window_for(started)
    ci = CheckIn(user_id=user.id, started_on=started, window_start=win_start, window_end=win_end)
    session.add(ci)
    await session.commit()
    ci = await _get(session, ci.id, user)
    return await _assemble(session, ci)


@router.get("", response_model=list[CheckInSummary])
async def list_check_ins(session: SessionDep, user: CurrentUser) -> list[CheckInSummary]:
    rows = (
        (
            await session.execute(
                owned(select(CheckIn), CheckIn, user).order_by(CheckIn.started_on.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        CheckInSummary(
            id=c.id,
            started_on=c.started_on,
            window_start=c.window_start,
            window_end=c.window_end,
            completed=c.completed,
        )
        for c in rows
    ]


@router.get("/{check_in_id}", response_model=CheckInView)
async def get_check_in(check_in_id: int, session: SessionDep, user: CurrentUser) -> CheckInView:
    return await _assemble(session, await _get(session, check_in_id, user))


@router.patch("/{check_in_id}", response_model=CheckInView)
async def set_reflections(
    check_in_id: int, body: Reflections, session: SessionDep, user: CurrentUser
) -> CheckInView:
    ci = await _get(session, check_in_id, user)
    if body.worked_on is not None:
        ci.worked_on = body.worked_on
    if body.struggles is not None:
        ci.struggles = body.struggles
    await session.commit()
    return await _assemble(session, await _get(session, check_in_id, user))


@router.post("/{check_in_id}/photos", response_model=PhotoOut, status_code=201)
async def add_photo(
    check_in_id: int,
    session: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
) -> PhotoOut:
    ci = await _get(session, check_in_id, user)
    dest_dir = UPLOAD_DIR / f"check-in-{ci.id}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / (file.filename or "photo")
    dest.write_bytes(await file.read())
    photo = CheckInPhoto(check_in_id=ci.id, storage_path=str(dest), content_type=file.content_type)
    session.add(photo)
    await session.commit()
    await session.refresh(photo)
    return PhotoOut(id=photo.id, storage_path=photo.storage_path, content_type=photo.content_type)


@router.post("/{check_in_id}/finish", response_model=CheckInView)
async def finish(check_in_id: int, session: SessionDep, user: CurrentUser) -> CheckInView:
    ci = await _get(session, check_in_id, user)
    ci.completed = True
    await session.commit()
    return await _assemble(session, await _get(session, check_in_id, user))
