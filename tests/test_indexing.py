import uuid

import pytest

from app.repositories.memory import InMemoryChunkRepository
from app.services.indexing import Indexer
from app.services.pdf import PdfExtractionError
from app.services.retrieval import Retriever
from tests.fakes import FakeEmbedder, make_pdf


@pytest.fixture
def chunks() -> InMemoryChunkRepository:
    return InMemoryChunkRepository()


@pytest.fixture
def indexer(chunks: InMemoryChunkRepository) -> Indexer:
    return Indexer(FakeEmbedder(), chunks, chunk_size=60, chunk_overlap=10)


def test_a_pdf_becomes_retrievable_passages(
    indexer: Indexer, chunks: InMemoryChunkRepository, user_id: uuid.UUID
) -> None:
    stored = indexer.index(user_id, "policy.pdf", make_pdf("refunds take 30 days"))

    assert stored == 1
    assert chunks.list_documents(user_id) == ["policy.pdf"]


def test_indexed_text_can_be_retrieved(
    indexer: Indexer, chunks: InMemoryChunkRepository, user_id: uuid.UUID
) -> None:
    """The point of the whole step: upload, then ask, and get it back."""
    indexer.index(user_id, "policy.pdf", make_pdf("refunds take 30 days"))

    found = Retriever(FakeEmbedder(), chunks).find(user_id, "refunds take 30 days")

    assert "refunds take 30 days" in found[0].content


def test_re_uploading_replaces_rather_than_duplicates(
    indexer: Indexer, chunks: InMemoryChunkRepository, user_id: uuid.UUID
) -> None:
    """Appending would spend half the context budget repeating one passage,
    and make the model sound more confident for having seen it twice."""
    pdf = make_pdf("refunds take 30 days")

    first = indexer.index(user_id, "policy.pdf", pdf)
    second = indexer.index(user_id, "policy.pdf", pdf)

    found = Retriever(FakeEmbedder(), chunks).find(user_id, "refunds take 30 days")
    assert first == second
    assert len(found) == first


def test_a_failed_extraction_stores_nothing(
    indexer: Indexer, chunks: InMemoryChunkRepository, user_id: uuid.UUID
) -> None:
    """A half-indexed document is worse than none: retrieval would serve it."""
    with pytest.raises(PdfExtractionError):
        indexer.index(user_id, "scan.pdf", make_pdf(""))

    assert chunks.list_documents(user_id) == []


def test_a_failed_reupload_leaves_the_previous_version_intact(
    indexer: Indexer, chunks: InMemoryChunkRepository, user_id: uuid.UUID
) -> None:
    """Extraction runs before the delete, so a bad second upload cannot
    destroy a good first one."""
    indexer.index(user_id, "policy.pdf", make_pdf("refunds take 30 days"))

    with pytest.raises(PdfExtractionError):
        indexer.index(user_id, "policy.pdf", b"not a pdf at all")

    assert chunks.list_documents(user_id) == ["policy.pdf"]


def test_one_users_upload_is_invisible_to_another(
    indexer: Indexer,
    chunks: InMemoryChunkRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    indexer.index(user_id, "private.pdf", make_pdf("the secret is 42"))

    assert chunks.list_documents(other_user_id) == []


def test_deleting_a_document_only_touches_that_users_copy(
    indexer: Indexer,
    chunks: InMemoryChunkRepository,
    user_id: uuid.UUID,
    other_user_id: uuid.UUID,
) -> None:
    pdf = make_pdf("shared file name")
    indexer.index(user_id, "notes.pdf", pdf)
    indexer.index(other_user_id, "notes.pdf", pdf)

    chunks.delete_document(user_id, "notes.pdf")

    assert chunks.list_documents(user_id) == []
    assert chunks.list_documents(other_user_id) == ["notes.pdf"]
