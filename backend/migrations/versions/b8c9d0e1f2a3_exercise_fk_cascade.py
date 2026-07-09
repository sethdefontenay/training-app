"""cascade exercise FKs so deleting a user with custom exercises succeeds

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-09

The FKs referencing exercise.id (prescription, set_entry, mobility_done, program_exercise)
had no ON DELETE action. When a user is deleted, their custom exercises (owner_id = them)
cascade-delete — but those rows still referenced the exercise, so the delete was blocked.
Recreate the four FKs with ON DELETE CASCADE. Global (owner_id NULL) exercises are never
deleted, so this only ever fires for a deleted user's own custom exercises.
"""

from alembic import op

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None

# (table, fk_constraint_name)
_FKS = [
    ("prescription", "prescription_exercise_id_fkey"),
    ("set_entry", "set_entry_exercise_id_fkey"),
    ("mobility_done", "mobility_done_exercise_id_fkey"),
    ("program_exercise", "program_exercise_exercise_id_fkey"),
]


def upgrade() -> None:
    for table, name in _FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(
            name, table, "exercise", ["exercise_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    for table, name in _FKS:
        op.drop_constraint(name, table, type_="foreignkey")
        op.create_foreign_key(name, table, "exercise", ["exercise_id"], ["id"])
