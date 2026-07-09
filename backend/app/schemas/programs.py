"""Workout planner request/response schemas."""

from pydantic import BaseModel


class ProgramExerciseOut(BaseModel):
    id: int
    exercise_slug: str
    exercise_name: str
    sets_x_reps: str
    prescribed_weight: str | None
    order: int


class ProgramOut(BaseModel):
    id: int
    name: str
    exercises: list[ProgramExerciseOut]


class ProgramCreate(BaseModel):
    name: str


class ProgramRename(BaseModel):
    name: str


class ExerciseAdd(BaseModel):
    exercise_slug: str
    sets_x_reps: str
    prescribed_weight: str | None = None
    order: int | None = None


class ExerciseEdit(BaseModel):
    sets_x_reps: str | None = None
    prescribed_weight: str | None = None
    order: int | None = None


class WeekdayProgramOut(BaseModel):
    weekday: str
    program_id: int


class AssignProgram(BaseModel):
    # program_id = the program to run on the weekday; null clears the assignment.
    program_id: int | None = None
