from app.embeddings.base import Embedder
from tests.fakes import FakeEmbedder


def test_the_same_text_always_gives_the_same_vector() -> None:
    embedder = FakeEmbedder()

    assert embedder.embed_query("refund policy") == embedder.embed_query(
        "refund policy"
    )


def test_different_text_gives_a_different_vector() -> None:
    embedder = FakeEmbedder()

    assert embedder.embed_query("refund policy") != embedder.embed_query("shipping")


def test_every_vector_has_the_declared_width() -> None:
    embedder = FakeEmbedder(dimensions=16)
    vectors = embedder.embed_documents(["one", "two", "three"])

    assert all(len(vector) == embedder.dimensions for vector in vectors)


def test_embedding_nothing_returns_nothing() -> None:
    assert FakeEmbedder().embed_documents([]) == []


def test_one_vector_is_returned_per_input_in_order() -> None:
    embedder = FakeEmbedder()
    texts = ["alpha", "beta", "gamma"]
    vectors = embedder.embed_documents(texts)

    assert len(vectors) == len(texts)
    assert vectors == [embedder.embed_query(text) for text in texts]


def test_the_fake_satisfies_the_protocol() -> None:
    """mypy proves the fake and the real embedder are interchangeable."""
    embedder: Embedder = FakeEmbedder()

    assert embedder.model_id == "fake"
