"""create document_chunks

Revision ID: c3a71f9e4d02
Revises: b05d08fb5171
Create Date: 2026-10-11

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op

revision: str = "c3a71f9e4d02"
down_revision: str | Sequence[str] | None = "b05d08fb5171"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIMENSIONS = 384


def upgrade() -> None:
    # Autogenerate cannot know about this: it diffs models against the schema
    # and has no concept of a missing extension. Without it the vector type
    # does not exist and create_table fails.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        # The width is frozen into history on purpose: a migration must build
        # the same schema a year from now, so it cannot read today's config.
        # model_id is what makes a later change detectable instead of silent.
        sa.Column(
            "embedding",
            pgvector.sqlalchemy.Vector(EMBEDDING_DIMENSIONS),
            nullable=False,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_document_chunks_user_id", "document_chunks", ["user_id"], unique=False
    )
    op.create_index(
        "ix_document_chunks_user_document",
        "document_chunks",
        ["user_id", "document_name"],
        unique=False,
    )
    # No vector index yet. HNSW and IVFFlat are both approximate, and a
    # sequential scan over a few thousand rows is exact and fast. IVFFlat in
    # particular clusters at build time, so building it on an empty table
    # gives permanently poor recall.


def downgrade() -> None:
    op.drop_index("ix_document_chunks_user_document", table_name="document_chunks")
    op.drop_index("ix_document_chunks_user_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    # The extension is deliberately left in place: other tables may come to
    # depend on it, and dropping a shared extension is not this migration's
    # business.
