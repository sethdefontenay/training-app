"""set_entry composite (session_id, exercise_id) index

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-12

Backs the hot per-exercise set-count lookups (daily/workout pages, set_index on logging)
with a composite index instead of relying on the single-column session_id index.
"""

from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_set_entry_session_exercise",
        "set_entry",
        ["session_id", "exercise_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_set_entry_session_exercise", table_name="set_entry")
