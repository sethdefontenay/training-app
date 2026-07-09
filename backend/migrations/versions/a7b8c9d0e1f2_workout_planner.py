"""workout planner: user-owned programs + weekday assignments

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-09

Purely additive — three new empty tables (workout_program, program_exercise,
weekday_program). No backfill; safe to run unattended on Railway boot.
"""

import sqlalchemy as sa
from alembic import op

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workout_program",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_workout_program_user_id", "workout_program", ["user_id"])

    op.create_table(
        "program_exercise",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("workout_program.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exercise_id", sa.Integer(), sa.ForeignKey("exercise.id"), nullable=False),
        sa.Column("sets_x_reps", sa.String(), nullable=False),
        sa.Column("prescribed_weight", sa.String(), nullable=True),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_program_exercise_program_id", "program_exercise", ["program_id"])
    op.create_index("ix_program_exercise_exercise_id", "program_exercise", ["exercise_id"])

    op.create_table(
        "weekday_program",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("weekday", sa.String(), nullable=False),
        sa.Column(
            "program_id",
            sa.Integer(),
            sa.ForeignKey("workout_program.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "weekday", name="uq_weekday_program_user_day"),
    )
    op.create_index("ix_weekday_program_user_id", "weekday_program", ["user_id"])
    op.create_index("ix_weekday_program_program_id", "weekday_program", ["program_id"])


def downgrade() -> None:
    op.drop_table("weekday_program")
    op.drop_table("program_exercise")
    op.drop_table("workout_program")
