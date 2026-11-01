"""add organisations and memberships

Revision ID: 005a57e99cd0
Revises: 409f9e6d475e
Create Date: 2026-11-01 06:47:49.139891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005a57e99cd0'
down_revision: Union[str, Sequence[str], None] = '409f9e6d475e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organisations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("organisation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_memberships_user"),
    )
    op.create_index("ix_memberships_organisation", "memberships", ["organisation_id"])

    # One organisation and one membership per existing user. Without this the
    # backfill below has nothing to point at: autogenerate would have added
    # the columns and left every existing row unassignable.
    op.execute(
        "INSERT INTO organisations (id, name) "
        "SELECT gen_random_uuid(), split_part(email, chr(64), 1) || chr(32) "
        "|| 'workspace' FROM users"
    )
    op.execute(
        "INSERT INTO memberships (id, user_id, organisation_id, role) "
        "SELECT gen_random_uuid(), u.id, o.id, 'owner' FROM users u "
        "JOIN LATERAL (SELECT id FROM organisations WHERE name = "
        "split_part(u.email, chr(64), 1) || chr(32) || 'workspace' LIMIT 1) "
        "o ON TRUE"
    )

    # Nullable, backfill, then NOT NULL. In production this is three deploys:
    # during a rolling deploy old code keeps inserting rows that know nothing
    # about the column. One migration is safe here only because no old code
    # is running.
    for table in ("conversations", "document_chunks", "artifacts"):
        op.add_column(table, sa.Column("organisation_id", sa.Uuid(), nullable=True))
        op.execute(
            f"UPDATE {table} AS t SET organisation_id = m.organisation_id "
            f"FROM memberships m WHERE m.user_id = t.user_id"
        )
        # A row whose owner no longer exists cannot be assigned a tenant, and
        # a row with no tenant sits outside every boundary.
        op.execute(f"DELETE FROM {table} WHERE organisation_id IS NULL")
        op.alter_column(table, "organisation_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table}_organisation",
            table,
            "organisations",
            ["organisation_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])


def downgrade() -> None:
    for table in ("artifacts", "document_chunks", "conversations"):
        op.drop_index(f"ix_{table}_organisation_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organisation", table, type_="foreignkey")
        op.drop_column(table, "organisation_id")

    op.drop_index("ix_memberships_organisation", table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("organisations")
