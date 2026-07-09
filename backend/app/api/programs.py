"""Workout planner endpoints: user-owned programs, their exercises, and the weekday
schedule. All rows are owner-scoped; the planner is universal (no capability gate)."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep, owned
from app.models import ProgramExercise, WeekdayProgram, WorkoutProgram
from app.schemas.programs import (
    AssignProgram,
    ExerciseAdd,
    ExerciseEdit,
    ProgramCreate,
    ProgramExerciseOut,
    ProgramOut,
    ProgramRename,
    WeekdayProgramOut,
)
from app.services.programs import import_training_days, list_programs, load_program
from app.services.workouts import get_or_create_exercise

router = APIRouter(prefix="/programs", tags=["planner"])

_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
_WEEKDAYS = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)


def _to_out(p: WorkoutProgram) -> ProgramOut:
    return ProgramOut(
        id=p.id,
        name=p.name,
        exercises=[
            ProgramExerciseOut(
                id=pe.id,
                exercise_slug=pe.exercise.slug,
                exercise_name=pe.exercise.name,
                sets_x_reps=pe.sets_x_reps,
                prescribed_weight=pe.prescribed_weight,
                order=pe.order,
            )
            for pe in sorted(p.exercises, key=lambda e: e.order)
        ],
    )


@router.get("", response_model=list[ProgramOut])
async def list_all(session: SessionDep, user: CurrentUser) -> list[ProgramOut]:
    return [_to_out(p) for p in await list_programs(session, user)]


@router.post("/import-training-days", status_code=status.HTTP_201_CREATED)
async def import_from_plan(session: SessionDep, user: CurrentUser) -> dict[str, int]:
    """Bootstrap programs from the current PT plan's training days + weekday schedule."""
    return await import_training_days(session, user)


@router.get("/schedule", response_model=list[WeekdayProgramOut])
async def get_schedule(session: SessionDep, user: CurrentUser) -> list[WeekdayProgramOut]:
    rows = (
        (await session.execute(owned(select(WeekdayProgram), WeekdayProgram, user))).scalars().all()
    )
    return [WeekdayProgramOut(weekday=r.weekday, program_id=r.program_id) for r in rows]


@router.put("/schedule/{weekday}", status_code=status.HTTP_200_OK)
async def assign_weekday(
    weekday: str, body: AssignProgram, session: SessionDep, user: CurrentUser
) -> dict[str, str | int | None]:
    weekday = weekday.lower()
    if weekday not in _WEEKDAYS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid weekday")
    existing = await session.scalar(
        owned(select(WeekdayProgram), WeekdayProgram, user).where(WeekdayProgram.weekday == weekday)
    )
    if body.program_id is None:
        # Clear the assignment; the weekday reverts to the PT-plan fallback.
        if existing is not None:
            await session.delete(existing)
            await session.commit()
        return {"weekday": weekday, "program_id": None}
    # Assigning: the program must belong to this user.
    program = await load_program(session, body.program_id, user)
    if program is None:
        raise _NOT_FOUND
    if existing is None:
        session.add(WeekdayProgram(user_id=user.id, weekday=weekday, program_id=program.id))
    else:
        existing.program_id = program.id
    await session.commit()
    return {"weekday": weekday, "program_id": program.id}


@router.post("", response_model=ProgramOut, status_code=status.HTTP_201_CREATED)
async def create_program(body: ProgramCreate, session: SessionDep, user: CurrentUser) -> ProgramOut:
    p = WorkoutProgram(user_id=user.id, name=body.name)
    session.add(p)
    await session.commit()
    await session.refresh(p)
    return ProgramOut(id=p.id, name=p.name, exercises=[])


@router.patch("/{program_id}", response_model=ProgramOut)
async def rename_program(
    program_id: int, body: ProgramRename, session: SessionDep, user: CurrentUser
) -> ProgramOut:
    p = await load_program(session, program_id, user)
    if p is None:
        raise _NOT_FOUND
    p.name = body.name
    await session.commit()
    return _to_out(await load_program(session, program_id, user))  # type: ignore[arg-type]


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_program(program_id: int, session: SessionDep, user: CurrentUser) -> None:
    p = await session.scalar(
        owned(select(WorkoutProgram), WorkoutProgram, user).where(WorkoutProgram.id == program_id)
    )
    if p is None:
        raise _NOT_FOUND
    # Cascade clears any WeekdayProgram assignment (FK ON DELETE CASCADE); those weekdays
    # fall back to the PT plan.
    await session.delete(p)
    await session.commit()


@router.post("/{program_id}/exercises", response_model=ProgramOut, status_code=201)
async def add_exercise(
    program_id: int, body: ExerciseAdd, session: SessionDep, user: CurrentUser
) -> ProgramOut:
    p = await load_program(session, program_id, user)
    if p is None:
        raise _NOT_FOUND
    ex = await get_or_create_exercise(session, body.exercise_slug, user.id)
    order = body.order if body.order is not None else len(p.exercises)
    session.add(
        ProgramExercise(
            program_id=p.id,
            exercise_id=ex.id,
            sets_x_reps=body.sets_x_reps,
            prescribed_weight=body.prescribed_weight or None,
            order=order,
        )
    )
    await session.commit()
    return _to_out(await load_program(session, program_id, user))  # type: ignore[arg-type]


async def _owned_program_exercise(
    session: SessionDep, program_id: int, pe_id: int, user: CurrentUser
) -> ProgramExercise:
    """A ProgramExercise scoped to a program the user owns (404 otherwise)."""
    pe = await session.scalar(
        select(ProgramExercise)
        .join(WorkoutProgram, WorkoutProgram.id == ProgramExercise.program_id)
        .where(
            ProgramExercise.id == pe_id,
            ProgramExercise.program_id == program_id,
            WorkoutProgram.user_id == user.id,
        )
    )
    if pe is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exercise not found")
    return pe


@router.patch("/{program_id}/exercises/{pe_id}", response_model=ProgramOut)
async def edit_exercise(
    program_id: int, pe_id: int, body: ExerciseEdit, session: SessionDep, user: CurrentUser
) -> ProgramOut:
    pe = await _owned_program_exercise(session, program_id, pe_id, user)
    if body.sets_x_reps is not None:
        pe.sets_x_reps = body.sets_x_reps
    if body.prescribed_weight is not None:
        pe.prescribed_weight = body.prescribed_weight or None
    if body.order is not None:
        pe.order = body.order
    await session.commit()
    return _to_out(await load_program(session, program_id, user))  # type: ignore[arg-type]


@router.delete("/{program_id}/exercises/{pe_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_exercise(
    program_id: int, pe_id: int, session: SessionDep, user: CurrentUser
) -> None:
    pe = await _owned_program_exercise(session, program_id, pe_id, user)
    await session.delete(pe)
    await session.commit()
