import uuid
from collections.abc import Callable

import pytest

from app.repositories.memory import InMemoryConversationRepository
from app.services.chat import ChatService
from tests.fakes import FakeLLMClient

ServiceFactory = Callable[..., tuple[ChatService, FakeLLMClient]]


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def make_service() -> ServiceFactory:
    """Build a ChatService wired to a fake client and in-memory storage.

    Construction lives here so that adding a constructor argument later is a
    one-line change instead of an edit in every test.
    """

    def _make(
        reply: str = "reply", max_history: int = 10
    ) -> tuple[ChatService, FakeLLMClient]:
        fake = FakeLLMClient(reply)
        service = ChatService(fake, InMemoryConversationRepository(), max_history)
        return service, fake

    return _make
