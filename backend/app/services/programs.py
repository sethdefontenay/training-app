"""Workout planner services: load/build user-owned programs and the weekday schedule."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Plan,
    ProgramExercise,
    TrainingDay,
    User,
    WeekdayProgram,
    WorkoutProgram,
)


async def load_program(session: AsyncSession, program_id: int, user: User) -> WorkoutProgram | None:
    """A single program owned by the user, with its exercises (+ each exercise) loaded."""
    p: WorkoutProgram | None = await session.scalar(
        select(WorkoutProgram)
        .where(WorkoutProgram.id == program_id, WorkoutProgram.user_id == user.id)
        .options(selectinload(WorkoutProgram.exercises).selectinload(ProgramExercise.exercise))
        # Refresh a possibly-cached instance so a reload after a mutation reflects the new
        # exercises even when the session keeps objects alive across commit.
        .execution_options(populate_existing=True)
    )
    return p


async def program_for_weekday(
    session: AsyncSession, user_id: int, weekday: str
) -> WorkoutProgram | None:
    """The program the user has assigned to this weekday (with exercises), or None.
    Used by the daily view: planner assignment takes precedence over the PT plan."""
    p: WorkoutProgram | None = await session.scalar(
        select(WorkoutProgram)
        .join(WeekdayProgram, WeekdayProgram.program_id == WorkoutProgram.id)
        .where(WeekdayProgram.user_id == user_id, WeekdayProgram.weekday == weekday)
        .options(selectinload(WorkoutProgram.exercises).selectinload(ProgramExercise.exercise))
    )
    return p


async def list_programs(session: AsyncSession, user: User) -> list[WorkoutProgram]:
    rows = (
        await session.scalars(
            select(WorkoutProgram)
            .where(WorkoutProgram.user_id == user.id)
            .order_by(WorkoutProgram.name)
            .options(selectinload(WorkoutProgram.exercises).selectinload(ProgramExercise.exercise))
        )
    ).all()
    return list(rows)


async def import_training_days(session: AsyncSession, user: User) -> dict[str, int]:
    """Create user-owned programs from the current PT plan's training days, and pre-assign
    each to the same weekday the plan scheduled it on. Non-destructive; skips programs
    whose name already exists (so re-running doesn't duplicate). Returns counts."""
    plan = await session.scalar(
        select(Plan)
        .where(Plan.is_current.is_(True), Plan.user_id == user.id)
        .options(
            selectinload(Plan.training_days).selectinload(TrainingDay.prescriptions),
            selectinload(Plan.schedule),
        )
    )
    if plan is None:
        return {"created": 0, "skipped": 0, "assigned": 0}

    by_name = {p.name: p for p in await list_programs(session, user)}
    td_to_program: dict[int, int] = {}
    created = skipped = 0

    for td in plan.training_days:
        if td.label in by_name:
            td_to_program[td.id] = by_name[td.label].id
            skipped += 1
            continue
        prog = WorkoutProgram(user_id=user.id, name=td.label)
        session.add(prog)
        await session.flush()
        for pr in sorted(td.prescriptions, key=lambda x: x.order):
            session.add(
                ProgramExercise(
                    program_id=prog.id,
                    exercise_id=pr.exercise_id,
                    sets_x_reps=pr.sets_x_reps,
                    prescribed_weight=pr.prescribed_weight,
                    order=pr.order,
                )
            )
        td_to_program[td.id] = prog.id
        by_name[td.label] = prog
        created += 1

    assigned = 0
    for ws in plan.schedule:
        if ws.training_day_id is None or ws.training_day_id not in td_to_program:
            continue
        program_id = td_to_program[ws.training_day_id]
        existing = await session.scalar(
            select(WeekdayProgram).where(
                WeekdayProgram.user_id == user.id, WeekdayProgram.weekday == ws.weekday
            )
        )
        if existing is None:
            session.add(WeekdayProgram(user_id=user.id, weekday=ws.weekday, program_id=program_id))
        else:
            existing.program_id = program_id
        assigned += 1

    await session.commit()
    return {"created": created, "skipped": skipped, "assigned": assigned}
