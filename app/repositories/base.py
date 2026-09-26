from typing import Protocol

from app.domain import Message


class ConversationRepository(Protocol):
    def get_history(
        self, conversation_id: str, limit: int | None = None
    ) -> list[Message]: ...

    def add_message(self, conversation_id: str, message: Message) -> None: ...
