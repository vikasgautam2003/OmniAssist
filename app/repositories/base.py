from typing import Protocol

from app.domain import Message, User


class EmailAlreadyExistsError(Exception):
    """Raised when a user with that email already exists.

    Vendor-neutral on purpose: a caller must never have to catch
    sqlalchemy.exc.IntegrityError, or the storage engine has leaked upward.
    """


class ConversationRepository(Protocol):
    def get_history(
        self, conversation_id: str, limit: int | None = None
    ) -> list[Message]: ...

    def add_message(self, conversation_id: str, message: Message) -> None: ...


class UserRepository(Protocol):
    def get_by_email(self, email: str) -> User | None: ...
    def create(self, email: str, password_hash: str) -> User: ...
