import math
import uuid

from app.domain import Chunk, Message, User, Vector
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


def cosine_distance(left: Vector, right: Vector) -> float:
    """1 - cosine similarity: 0 is identical, 2 is opposite.

    Written out rather than imported so the behaviour of pgvector's `<=>`
    operator is visible and testable without a database.
    """
    dot = sum(x * y for x, y in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(x * x for x in left))
    right_norm = math.sqrt(sum(y * y for y in right))

    if not left_norm or not right_norm:
        return 1.0

    return 1.0 - dot / (left_norm * right_norm)


class InMemoryChunkRepository:
    def __init__(self) -> None:
        self._rows: list[tuple[uuid.UUID, Chunk, Vector]] = []

    def add(
        self,
        user_id: uuid.UUID,
        document_name: str,
        chunks: list[str],
        vectors: list[Vector],
        model_id: str,
    ) -> None:
        if len(chunks) != len(vectors):
            raise ValueError(
                f"Got {len(chunks)} chunks and {len(vectors)} vectors; "
                "they must correspond one to one."
            )

        for index, (content, vector) in enumerate(zip(chunks, vectors, strict=True)):
            chunk = Chunk(
                content=content, document_name=document_name, chunk_index=index
            )
            self._rows.append((user_id, chunk, vector))

    def search(self, user_id: uuid.UUID, vector: Vector, limit: int) -> list[Chunk]:
        owned = [row for row in self._rows if row[0] == user_id]
        ranked = sorted(owned, key=lambda row: cosine_distance(vector, row[2]))
        return [chunk for _, chunk, _ in ranked[:limit]]
