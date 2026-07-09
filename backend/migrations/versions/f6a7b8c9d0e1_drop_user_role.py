"""drop the retired user.role column (owner/trainer axis removed for multiuser)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-09

Multiuser makes every user an independent owner; the read-only trainer role and its
guard are gone. Drop the now-unused column.
"""

import sqlalchemy as sa
from alembic import op

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("user", "role")


def downgrade() -> None:
    op.add_column(
        "user", sa.Column("role", sa.String(), nullable=False, server_default="owner")
    )
