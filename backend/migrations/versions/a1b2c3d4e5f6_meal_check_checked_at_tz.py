"""make meal_check.checked_at timezone-aware

The column was created as TIMESTAMP WITHOUT TIME ZONE, but the meal-check
endpoint writes datetime.now(UTC) (tz-aware). asyncpg rejects a tz-aware value
into a naive column, so checking a meal 500'd in production. Convert it to
TIMESTAMP WITH TIME ZONE to match every other timestamp in the schema.

Revision ID: a1b2c3d4e5f6
Revises: 6f37418abe3a
Create Date: 2026-06-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6f37418abe3a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'meal_check',
        'checked_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using="checked_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'meal_check',
        'checked_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
