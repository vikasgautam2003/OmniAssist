import uuid
from collections.abc import Callable

import pytest

from app.domain import Scope
from app.repositories.memory import InMemoryConversationRepository
from app.services.chat import ChatService
from app.services.retrieval import Retriever
from app.tools.registry import ToolRegistry
from tests.fakes import FakeLLMClient

ServiceFactory = Callable[..., tuple[ChatService, FakeLLMClient]]


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def organisation_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def scope(organisation_id: uuid.UUID, user_id: uuid.UUID) -> Scope:
    return Scope(organisation_id=organisation_id, user_id=user_id)


@pytest.fixture
def other_scope(other_user_id: uuid.UUID) -> Scope:
    """A different user in a different organisation -- the case that matters."""
    return Scope(organisation_id=uuid.uuid4(), user_id=other_user_id)


@pytest.fixture
def colleague_scope(organisation_id: uuid.UUID, other_user_id: uuid.UUID) -> Scope:
    """A different user in the *same* organisation: shares documents, not chats."""
    return Scope(organisation_id=organisation_id, user_id=other_user_id)


@pytest.fixture
def make_service() -> ServiceFactory:
    """Build a ChatService wired to a fake client and in-memory storage.

    Construction lives here so that adding a constructor argument later is a
    one-line change instead of an edit in every test.
    """

    def _make(
        reply: str = "reply",
        max_history: int = 10,
        retriever: Retriever | None = None,
        tools: ToolRegistry | None = None,
        tool_calls: object = (),
        max_tool_iterations: int = 5,
    ) -> tuple[ChatService, FakeLLMClient]:
        fake = FakeLLMClient(reply, tool_calls=tool_calls)  # type: ignore[arg-type]
        service = ChatService(
            fake,
            InMemoryConversationRepository(),
            max_history,
            retriever=retriever,
            tools=tools,
            max_tool_iterations=max_tool_iterations,
        )
        return service, fake

    return _make
