import uuid

from app.domain import Message, User
from app.repositories.base import ConversationNotFoundError, EmailAlreadyExistsError


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}
        self._owners: dict[str, uuid.UUID] = {}

    def get_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[Message]:
        # Another user's conversation is indistinguishable from one that does
        # not exist: confirming existence would let ids be enumerated.
        if self._owners.get(conversation_id) != user_id:
            return []

        history = self._store.get(conversation_id, [])

        if limit is None:
            return list(history)

        return list(history[-limit:])

    def add_message(
        self, conversation_id: str, user_id: uuid.UUID, message: Message
    ) -> None:
        owner = self._owners.setdefault(conversation_id, user_id)

        if owner != user_id:
            raise ConversationNotFoundError(conversation_id)

        self._store.setdefault(conversation_id, []).append(message)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}
        self._by_id: dict[uuid.UUID, User] = {}

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self._by_id.get(user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email)

    def create(self, email: str, password_hash: str) -> User:
        if email in self._by_email:
            raise EmailAlreadyExistsError(email)

        user = User(id=uuid.uuid4(), email=email, password_hash=password_hash)
        self._by_email[email] = user
        self._by_id[user.id] = user
        return user
