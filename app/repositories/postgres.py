import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.db.models import Conversation, MessageRow, UserRow
from app.db.session import get_session_factory
from app.domain import Message, User
from app.repositories.base import ConversationNotFoundError, EmailAlreadyExistsError


class PostgresConversationRepository:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def get_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[Message]:
        # Ownership is part of the query, not a check beside it: there is no
        # way to read this conversation without also proving it is the
        # caller's. A check in the service layer could be forgotten by the
        # next code path that needs messages.
        query = (
            select(MessageRow)
            .join(Conversation, Conversation.id == MessageRow.conversation_id)
            .where(
                MessageRow.conversation_id == conversation_id,
                Conversation.user_id == user_id,
            )
        )

        with self._session_factory() as session:
            if limit is None:
                rows = list(
                    session.scalars(
                        query.order_by(MessageRow.created_at, MessageRow.id)
                    ).all()
                )
            else:
                # Newest-first so the index can satisfy the LIMIT without a
                # full scan; reversed afterwards because the model needs the
                # conversation in chronological order.
                rows = list(
                    reversed(
                        session.scalars(
                            query.order_by(
                                MessageRow.created_at.desc(),
                                MessageRow.id.desc(),
                            ).limit(limit)
                        ).all()
                    )
                )

            return [{"role": row.role, "content": row.content} for row in rows]

    def add_message(
        self, conversation_id: str, user_id: uuid.UUID, message: Message
    ) -> None:
        with self._session_factory() as session:
            # Atomic upsert rather than SELECT-then-INSERT: two concurrent
            # requests opening the same conversation would both see it missing
            # and the second INSERT would raise a duplicate-key error.
            session.execute(
                pg_insert(Conversation)
                .values(id=conversation_id, user_id=user_id)
                .on_conflict_do_nothing(index_elements=["id"])
            )

            # The upsert does nothing when the id already exists -- including
            # when it belongs to somebody else. Without this check a user could
            # write into another user's conversation by guessing its id.
            owner = session.scalar(
                select(Conversation.user_id).where(Conversation.id == conversation_id)
            )

            if owner != user_id:
                raise ConversationNotFoundError(conversation_id)

            session.add(
                MessageRow(
                    conversation_id=conversation_id,
                    role=message["role"],
                    content=message["content"],
                )
            )

            session.commit()


class PostgresUserRepository:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        with self._session_factory() as session:
            row = session.get(UserRow, user_id)

            if row is None:
                return None

            return User(id=row.id, email=row.email, password_hash=row.password_hash)

    def get_by_email(self, email: str) -> User | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(UserRow).where(UserRow.email == email)
            ).one_or_none()

            if row is None:
                return None

            return User(id=row.id, email=row.email, password_hash=row.password_hash)

    def create(self, email: str, password_hash: str) -> User:
        with self._session_factory() as session:
            row = UserRow(email=email, password_hash=password_hash)
            session.add(row)

            try:
                session.commit()
            except IntegrityError as exc:
                # The unique constraint is the real guarantee; translate the
                # driver's exception so callers never import sqlalchemy.
                session.rollback()
                raise EmailAlreadyExistsError(email) from exc

            return User(id=row.id, email=row.email, password_hash=row.password_hash)
