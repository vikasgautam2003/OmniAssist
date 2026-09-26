from app.clients.base import Message


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
