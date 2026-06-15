"""user.role for read-only trainer access

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-16

Adds a role column to user. Existing rows become "owner" (full access) via the
server default; "trainer" is the read-only coach login.
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("role", sa.String(), nullable=False, server_default="owner"),
    )


def downgrade() -> None:
    op.drop_column("user", "role")
