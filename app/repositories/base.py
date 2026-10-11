import uuid
from typing import Protocol

from app.domain import Chunk, Message, User, Vector


class EmailAlreadyExistsError(Exception):
    """Raised when a user with that email already exists.

    Vendor-neutral on purpose: a caller must never have to catch
    sqlalchemy.exc.IntegrityError, or the storage engine has leaked upward.
    """


class ConversationNotFoundError(Exception):
    """Raised when a conversation does not exist, or is not the caller's.

    Deliberately one error for both: telling a caller that a conversation
    exists but belongs to someone else lets them enumerate real ids.
    """


class ConversationRepository(Protocol):
    def get_history(
        self,
        conversation_id: str,
        user_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[Message]: ...

    def add_message(
        self, conversation_id: str, user_id: uuid.UUID, message: Message
    ) -> None: ...


class UserRepository(Protocol):
    def get_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...
    def create(self, email: str, password_hash: str) -> User: ...


class ChunkRepository(Protocol):
    def add(
        self,
        user_id: uuid.UUID,
        document_name: str,
        chunks: list[str],
        vectors: list[Vector],
        model_id: str,
    ) -> None: ...

    def search(self, user_id: uuid.UUID, vector: Vector, limit: int) -> list[Chunk]: ...
