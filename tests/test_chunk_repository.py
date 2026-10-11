import uuid

import pytest

from app.domain import Chunk
from app.repositories.base import ChunkRepository
from app.repositories.memory import InMemoryChunkRepository
from tests.fakes import FakeEmbedder


@pytest.fixture
def repository() -> InMemoryChunkRepository:
    return InMemoryChunkRepository()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


def store(repository, embedder, user_id, document_name, texts) -> None:
    repository.add(
        user_id=user_id,
        document_name=document_name,
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )


def test_stored_chunks_come_back(repository, embedder, user_id) -> None:
    store(repository, embedder, user_id, "policy.pdf", ["refund window is 30 days"])

    found = repository.search(
        user_id, embedder.embed_query("refund window is 30 days"), limit=5
    )

    assert [chunk.content for chunk in found] == ["refund window is 30 days"]


def test_another_users_chunks_are_invisible(
    repository, embedder, user_id, other_user_id
) -> None:
    """The one that matters: unscoped retrieval answers one user from
    another's documents, and nothing about the response looks wrong."""
    store(repository, embedder, user_id, "private.pdf", ["the secret is 42"])

    found = repository.search(
        other_user_id, embedder.embed_query("the secret is 42"), limit=5
    )

    assert found == []


def test_results_are_ordered_by_similarity(repository, embedder, user_id) -> None:
    texts = ["alpha text", "beta text", "gamma text"]
    store(repository, embedder, user_id, "doc.pdf", texts)

    found = repository.search(user_id, embedder.embed_query("beta text"), limit=3)

    assert found[0].content == "beta text"


def test_limit_is_respected(repository, embedder, user_id) -> None:
    store(repository, embedder, user_id, "doc.pdf", [f"passage {i}" for i in range(10)])

    found = repository.search(user_id, embedder.embed_query("passage 3"), limit=4)

    assert len(found) == 4


def test_searching_an_empty_store_returns_nothing(
    repository, embedder, user_id
) -> None:
    assert repository.search(user_id, embedder.embed_query("anything"), limit=5) == []


def test_mismatched_chunks_and_vectors_are_rejected(
    repository, embedder, user_id
) -> None:
    """Pairing chunk 3 with vector 4 would store text under the wrong meaning,
    and every search afterwards would be quietly wrong."""
    with pytest.raises(ValueError):
        repository.add(
            user_id=user_id,
            document_name="doc.pdf",
            chunks=["one", "two", "three"],
            vectors=embedder.embed_documents(["one", "two"]),
            model_id=embedder.model_id,
        )


def test_chunks_keep_their_position_and_document(repository, embedder, user_id) -> None:
    texts = ["first", "second", "third"]
    store(repository, embedder, user_id, "report.pdf", texts)

    found = repository.search(user_id, embedder.embed_query("second"), limit=1)

    assert found[0] == Chunk(
        content="second", document_name="report.pdf", chunk_index=1
    )


def test_the_in_memory_repository_satisfies_the_protocol() -> None:
    repository: ChunkRepository = InMemoryChunkRepository()

    assert repository.search(uuid.uuid4(), [0.0, 1.0], limit=1) == []
