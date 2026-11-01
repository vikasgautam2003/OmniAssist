import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.embeddings.base import EMBEDDING_DIMENSIONS


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)

    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Nullable because most turns are not tool turns. A tool call is a turn in
    # the conversation, so it belongs on this table rather than beside it.
    tool_calls: Mapped[list[dict[str, str]] | None] = mapped_column(JSON, nullable=True)

    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        Index(
            "ix_messages_conversation_created",
            "conversation_id",
            "created_at",
        ),
    )


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DocumentChunk(Base):
    """A chunk of an uploaded document, stored with the vector that finds it."""

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Kept alongside organisation_id: who uploaded it is worth knowing even
    # though retrieval is scoped to the organisation.
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    document_name: Mapped[str] = mapped_column(String(255), nullable=False)

    chunk_index: Mapped[int] = mapped_column(nullable=False)

    content: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=False
    )

    model_id: Mapped[str] = mapped_column(String(100), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_document_chunks_user_document", "user_id", "document_name"),
    )


class ArtifactRow(Base):
    """A file produced by a tool.

    Stored in PostgreSQL rather than on disk: a container filesystem is
    ephemeral, which matters for v0.4's deployment, and bytes in a column
    cannot be reached by a path-traversal bug. Object storage is the right
    answer once files get large -- the repository interface makes that a
    one-file change.
    """

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class OrganisationRow(Base):
    """A tenant. Every owned row belongs to exactly one."""

    __tablename__ = "organisations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MembershipRow(Base):
    """Which user belongs to which organisation, and with what role.

    A separate table rather than a column on users, because many-to-many is
    where this goes next -- a user belonging to several organisations needs an
    active-org claim in the token and a switcher in the UI, which is deferred,
    not rejected. The unique constraint enforces one-org-per-user for now.
    """

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organisations.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_memberships_user"),
        Index("ix_memberships_organisation", "organisation_id"),
    )
