import uuid

from app.domain import Message, User
from app.repositories.base import EmailAlreadyExistsError


class InMemoryConversationRepository:
    def __init__(self) -> None:
        self._store: dict[str, list[Message]] = {}

    def get_history(
        self,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        history = self._store.get(conversation_id, [])

        if limit is None:
            return list(history)

        return list(history[-limit:])

    def add_message(
        self,
        conversation_id: str,
        message: Message,
    ) -> None:
        self._store.setdefault(conversation_id, []).append(message)


class InMemoryUserRepository:
    def __init__(self) -> None:
        self._by_email: dict[str, User] = {}

    def get_by_email(self, email: str) -> User | None:
        return self._by_email.get(email)

    def create(self, email: str, password_hash: str) -> User:
        if email in self._by_email:
            raise EmailAlreadyExistsError(email)

        user = User(id=uuid.uuid4(), email=email, password_hash=password_hash)
        self._by_email[email] = user
        return user
