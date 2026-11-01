import pytest

from app.repositories.memory import InMemoryChunkRepository
from app.services.retrieval import Retriever
from tests.fakes import FakeEmbedder


@pytest.fixture
def chunks() -> InMemoryChunkRepository:
    return InMemoryChunkRepository()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


def seed(chunks, embedder, scope, document_name, texts) -> None:
    chunks.add(
        scope=scope,
        document_name=document_name,
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )


def test_the_closest_passage_is_returned(chunks, embedder, scope) -> None:
    seed(
        chunks,
        embedder,
        scope,
        "policy.pdf",
        ["refunds take 30 days", "we ship on Fridays"],
    )

    found = Retriever(embedder, chunks).find(scope, "refunds take 30 days")

    assert found[0].content == "refunds take 30 days"


def test_top_k_limits_how_much_context_is_pulled(chunks, embedder, scope) -> None:
    seed(chunks, embedder, scope, "doc.pdf", [f"passage {i}" for i in range(10)])

    found = Retriever(embedder, chunks, top_k=3).find(scope, "passage 4")

    assert len(found) == 3


def test_retrieval_is_scoped_to_the_asking_user(
    chunks, embedder, scope, other_scope
) -> None:
    seed(chunks, embedder, scope, "private.pdf", ["the secret is 42"])

    found = Retriever(embedder, chunks).find(other_scope, "the secret is 42")

    assert found == []


def test_a_blank_question_retrieves_nothing(chunks, embedder, scope) -> None:
    """Embedding whitespace would return an arbitrary nearest neighbour and
    present it to the model as relevant context."""
    seed(chunks, embedder, scope, "doc.pdf", ["something"])

    assert Retriever(embedder, chunks).find(scope, "   ") == []


def test_nothing_stored_means_nothing_found(chunks, embedder, scope) -> None:
    assert Retriever(embedder, chunks).find(scope, "anything at all") == []


def test_citation_details_survive_retrieval(chunks, embedder, scope) -> None:
    seed(chunks, embedder, scope, "report.pdf", ["alpha", "beta", "gamma"])

    found = Retriever(embedder, chunks, top_k=1).find(scope, "beta")

    assert found[0].document_name == "report.pdf"
    assert found[0].chunk_index == 1
