from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Conversation, MessageRow
from app.db.session import get_session_factory
from app.domain import Message


class PostgresConversationRepository:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def get_history(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        query = select(MessageRow).where(MessageRow.conversation_id == conversation_id)

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

    def add_message(self, conversation_id: str, message: Message) -> None:
        with self._session_factory() as session:
            # Atomic upsert rather than SELECT-then-INSERT: two concurrent
            # requests opening the same conversation would both see it missing
            # and the second INSERT would raise a duplicate-key error.
            session.execute(
                pg_insert(Conversation)
                .values(id=conversation_id)
                .on_conflict_do_nothing(index_elements=["id"])
            )

            session.add(
                MessageRow(
                    conversation_id=conversation_id,
                    role=message["role"],
                    content=message["content"],
                )
            )

            session.commit()
