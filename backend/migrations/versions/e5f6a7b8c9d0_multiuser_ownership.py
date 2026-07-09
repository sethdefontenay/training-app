"""multiuser: per-user ownership, capability flags, invites, exercise catalog

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-09

Converts the single-user schema to multiuser. Runs unattended on Railway boot, so
it is ordered to be safe against existing production data:

  1. Add nullable `user_id` to every root domain table, the capability/admin/timezone
     columns on `user`, `exercise.owner_id`, and the `invite` table.
  2. Backfill: stamp every existing row to the current owner (the lowest user id), and
     elevate that owner (is_admin + all capability flags on).
  3. Enforce NOT NULL on `user_id`.
  4. Rework the single-user unique constraints into per-user composites, and set up the
     shared-base/per-user-custom exercise uniqueness.

The whole migration runs in one transaction (Postgres transactional DDL), so it is
all-or-nothing. The backfill no-ops on a fresh database with no users.
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

# Root domain tables that gain a required owner FK (children inherit via their parent).
ROOT_TABLES = [
    "plan",
    "session",
    "mobility_done",
    "meal_check",
    "daily_wellbeing",
    "daily_log",
    "measurement",
    "steps_day",
    "sleep_night",
    "glucose_reading",
    "insulin_event",
    "check_in",
    "shopping_list",
]

# Tables whose single-column `date` UNIQUE index becomes a per-user (user_id, date) unique.
DATE_UNIQUE_TABLES = [
    "daily_wellbeing",
    "daily_log",
    "measurement",
    "steps_day",
    "sleep_night",
]


def upgrade() -> None:
    # --- 1. Additive: nullable columns + new table -------------------------------------
    for table in ROOT_TABLES:
        op.add_column(
            table,
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=True,
            ),
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])

    op.add_column(
        "user", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "user", sa.Column("has_diabetes", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "user",
        sa.Column("has_health_integrations", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "user", sa.Column("has_checkins", sa.Boolean(), nullable=False, server_default="false")
    )
    op.add_column(
        "user",
        sa.Column("timezone", sa.String(), nullable=False, server_default="Pacific/Auckland"),
    )

    op.add_column(
        "exercise",
        sa.Column(
            "owner_id", sa.Integer(), sa.ForeignKey("user.id", ondelete="CASCADE"), nullable=True
        ),
    )
    op.create_index("ix_exercise_owner_id", "exercise", ["owner_id"])

    op.create_table(
        "invite",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_invite_code", "invite", ["code"], unique=True)
    op.create_index("ix_invite_created_by", "invite", ["created_by"])

    # --- 2. Backfill existing data to the current owner --------------------------------
    conn = op.get_bind()
    owner_id = conn.execute(sa.text('SELECT id FROM "user" ORDER BY id LIMIT 1')).scalar()
    if owner_id is not None:
        for table in ROOT_TABLES:
            conn.execute(
                sa.text(f'UPDATE "{table}" SET user_id = :oid WHERE user_id IS NULL'),
                {"oid": owner_id},
            )
        conn.execute(
            sa.text(
                'UPDATE "user" SET is_admin = true, has_diabetes = true, '
                "has_health_integrations = true, has_checkins = true WHERE id = :oid"
            ),
            {"oid": owner_id},
        )

    # --- 3. Enforce NOT NULL -----------------------------------------------------------
    for table in ROOT_TABLES:
        op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=False)

    # --- 4. Rework uniqueness ----------------------------------------------------------
    # date-unique tables: single-column unique index -> per-user (user_id, date) unique.
    for table in DATE_UNIQUE_TABLES:
        op.drop_index(f"ix_{table}_date", table_name=table)
        op.create_index(f"ix_{table}_date", table, ["date"])  # keep a plain lookup index
        op.create_unique_constraint(f"uq_{table}_user_date", table, ["user_id", "date"])

    # mobility_done / meal_check: prepend user_id to the composite unique.
    op.drop_constraint("uq_mobility_done_day_ex", "mobility_done", type_="unique")
    op.create_unique_constraint(
        "uq_mobility_done_day_ex", "mobility_done", ["user_id", "date", "exercise_id"]
    )
    op.drop_constraint("uq_meal_check_day_meal", "meal_check", type_="unique")
    op.create_unique_constraint(
        "uq_meal_check_day_meal", "meal_check", ["user_id", "date", "meal_id"]
    )

    # plan: at most one current plan per user.
    op.create_index(
        "uq_plan_current_per_user",
        "plan",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_current"),
    )

    # exercise: shared base (owner_id IS NULL, globally unique slug) + per-user custom.
    op.drop_index("ix_exercise_slug", table_name="exercise")
    op.create_index("ix_exercise_slug", "exercise", ["slug"])  # plain lookup index
    op.create_unique_constraint("uq_exercise_owner_slug", "exercise", ["owner_id", "slug"])
    op.create_index(
        "uq_exercise_global_slug",
        "exercise",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )


def downgrade() -> None:
    # Reverse of section 4.
    op.drop_index("uq_exercise_global_slug", table_name="exercise")
    op.drop_constraint("uq_exercise_owner_slug", "exercise", type_="unique")
    op.drop_index("ix_exercise_slug", table_name="exercise")
    op.create_index("ix_exercise_slug", "exercise", ["slug"], unique=True)

    op.drop_index("uq_plan_current_per_user", table_name="plan")

    op.drop_constraint("uq_meal_check_day_meal", "meal_check", type_="unique")
    op.create_unique_constraint("uq_meal_check_day_meal", "meal_check", ["date", "meal_id"])
    op.drop_constraint("uq_mobility_done_day_ex", "mobility_done", type_="unique")
    op.create_unique_constraint("uq_mobility_done_day_ex", "mobility_done", ["date", "exercise_id"])

    for table in DATE_UNIQUE_TABLES:
        op.drop_constraint(f"uq_{table}_user_date", table, type_="unique")
        op.drop_index(f"ix_{table}_date", table_name=table)
        op.create_index(f"ix_{table}_date", table, ["date"], unique=True)

    # Reverse of section 1.
    op.drop_index("ix_invite_created_by", table_name="invite")
    op.drop_index("ix_invite_code", table_name="invite")
    op.drop_table("invite")

    op.drop_index("ix_exercise_owner_id", table_name="exercise")
    op.drop_column("exercise", "owner_id")

    for col in (
        "timezone",
        "has_checkins",
        "has_health_integrations",
        "has_diabetes",
        "is_admin",
    ):
        op.drop_column("user", col)

    for table in ROOT_TABLES:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
