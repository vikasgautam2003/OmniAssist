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


def seed(chunks, embedder, user_id, document_name, texts) -> None:
    chunks.add(
        user_id=user_id,
        document_name=document_name,
        chunks=texts,
        vectors=embedder.embed_documents(texts),
        model_id=embedder.model_id,
    )


def test_the_closest_passage_is_returned(chunks, embedder, user_id) -> None:
    seed(
        chunks,
        embedder,
        user_id,
        "policy.pdf",
        ["refunds take 30 days", "we ship on Fridays"],
    )

    found = Retriever(embedder, chunks).find(user_id, "refunds take 30 days")

    assert found[0].content == "refunds take 30 days"


def test_top_k_limits_how_much_context_is_pulled(chunks, embedder, user_id) -> None:
    seed(chunks, embedder, user_id, "doc.pdf", [f"passage {i}" for i in range(10)])

    found = Retriever(embedder, chunks, top_k=3).find(user_id, "passage 4")

    assert len(found) == 3


def test_retrieval_is_scoped_to_the_asking_user(
    chunks, embedder, user_id, other_user_id
) -> None:
    seed(chunks, embedder, user_id, "private.pdf", ["the secret is 42"])

    found = Retriever(embedder, chunks).find(other_user_id, "the secret is 42")

    assert found == []


def test_a_blank_question_retrieves_nothing(chunks, embedder, user_id) -> None:
    """Embedding whitespace would return an arbitrary nearest neighbour and
    present it to the model as relevant context."""
    seed(chunks, embedder, user_id, "doc.pdf", ["something"])

    assert Retriever(embedder, chunks).find(user_id, "   ") == []


def test_nothing_stored_means_nothing_found(chunks, embedder, user_id) -> None:
    assert Retriever(embedder, chunks).find(user_id, "anything at all") == []


def test_citation_details_survive_retrieval(chunks, embedder, user_id) -> None:
    seed(chunks, embedder, user_id, "report.pdf", ["alpha", "beta", "gamma"])

    found = Retriever(embedder, chunks, top_k=1).find(user_id, "beta")

    assert found[0].document_name == "report.pdf"
    assert found[0].chunk_index == 1
