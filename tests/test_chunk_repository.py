import uuid

import pytest

from app.domain import Chunk, Scope
from app.repositories.base import ChunkRepository
from app.repositories.memory import InMemoryChunkRepository
from tests.fakes import FakeEmbedder


@pytest.fixture
def repository() -> InMemoryChunkRepository:
    return InMemoryChunkRepository()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


def store(repository, embedder, scope, document_name, texts) -> None:
    repository.add(
        scope=scope,
        document_name=document_name,
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )


def test_stored_chunks_come_back(repository, embedder, scope) -> None:
    store(repository, embedder, scope, "policy.pdf", ["refund window is 30 days"])

    found = repository.search(
        scope, embedder.embed_query("refund window is 30 days"), limit=5
    )

    assert [chunk.content for chunk in found] == ["refund window is 30 days"]


def test_another_organisations_chunks_are_invisible(
    repository, embedder, scope, other_scope
) -> None:
    """The one that matters: unscoped retrieval answers one user from
    another's documents, and nothing about the response looks wrong."""
    store(repository, embedder, scope, "private.pdf", ["the secret is 42"])

    found = repository.search(
        other_scope, embedder.embed_query("the secret is 42"), limit=5
    )

    assert found == []


def test_results_are_ordered_by_similarity(repository, embedder, scope) -> None:
    texts = ["alpha text", "beta text", "gamma text"]
    store(repository, embedder, scope, "doc.pdf", texts)

    found = repository.search(scope, embedder.embed_query("beta text"), limit=3)

    assert found[0].content == "beta text"


def test_limit_is_respected(repository, embedder, scope) -> None:
    store(repository, embedder, scope, "doc.pdf", [f"passage {i}" for i in range(10)])

    found = repository.search(scope, embedder.embed_query("passage 3"), limit=4)

    assert len(found) == 4


def test_searching_an_empty_store_returns_nothing(repository, embedder, scope) -> None:
    assert repository.search(scope, embedder.embed_query("anything"), limit=5) == []


def test_mismatched_chunks_and_vectors_are_rejected(
    repository, embedder, scope
) -> None:
    """Pairing chunk 3 with vector 4 would store text under the wrong meaning,
    and every search afterwards would be quietly wrong."""
    with pytest.raises(ValueError):
        repository.add(
            scope=scope,
            document_name="doc.pdf",
            chunks=["one", "two", "three"],
            vectors=embedder.embed_documents(["one", "two"]),
            model_id=embedder.model_id,
        )


def test_chunks_keep_their_position_and_document(repository, embedder, scope) -> None:
    texts = ["first", "second", "third"]
    store(repository, embedder, scope, "report.pdf", texts)

    found = repository.search(scope, embedder.embed_query("second"), limit=1)

    assert found[0] == Chunk(
        content="second", document_name="report.pdf", chunk_index=1
    )


def test_the_in_memory_repository_satisfies_the_protocol() -> None:
    repository: ChunkRepository = InMemoryChunkRepository()

    assert (
        repository.search(
            Scope(organisation_id=uuid.uuid4(), user_id=uuid.uuid4()),
            [0.0, 1.0],
            limit=1,
        )
        == []
    )
