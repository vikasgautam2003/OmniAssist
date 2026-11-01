import pytest

from app.domain import Scope
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
    indexer: Indexer, chunks: InMemoryChunkRepository, scope: Scope
) -> None:
    stored = indexer.index(scope, "policy.pdf", make_pdf("refunds take 30 days"))

    assert stored == 1
    assert chunks.list_documents(scope) == ["policy.pdf"]


def test_indexed_text_can_be_retrieved(
    indexer: Indexer, chunks: InMemoryChunkRepository, scope: Scope
) -> None:
    """The point of the whole step: upload, then ask, and get it back."""
    indexer.index(scope, "policy.pdf", make_pdf("refunds take 30 days"))

    found = Retriever(FakeEmbedder(), chunks).find(scope, "refunds take 30 days")

    assert "refunds take 30 days" in found[0].content


def test_re_uploading_replaces_rather_than_duplicates(
    indexer: Indexer, chunks: InMemoryChunkRepository, scope: Scope
) -> None:
    """Appending would spend half the context budget repeating one passage,
    and make the model sound more confident for having seen it twice."""
    pdf = make_pdf("refunds take 30 days")

    first = indexer.index(scope, "policy.pdf", pdf)
    second = indexer.index(scope, "policy.pdf", pdf)

    found = Retriever(FakeEmbedder(), chunks).find(scope, "refunds take 30 days")
    assert first == second
    assert len(found) == first


def test_a_failed_extraction_stores_nothing(
    indexer: Indexer, chunks: InMemoryChunkRepository, scope: Scope
) -> None:
    """A half-indexed document is worse than none: retrieval would serve it."""
    with pytest.raises(PdfExtractionError):
        indexer.index(scope, "scan.pdf", make_pdf(""))

    assert chunks.list_documents(scope) == []


def test_a_failed_reupload_leaves_the_previous_version_intact(
    indexer: Indexer, chunks: InMemoryChunkRepository, scope: Scope
) -> None:
    """Extraction runs before the delete, so a bad second upload cannot
    destroy a good first one."""
    indexer.index(scope, "policy.pdf", make_pdf("refunds take 30 days"))

    with pytest.raises(PdfExtractionError):
        indexer.index(scope, "policy.pdf", b"not a pdf at all")

    assert chunks.list_documents(scope) == ["policy.pdf"]


def test_another_organisations_upload_is_invisible(
    indexer: Indexer,
    chunks: InMemoryChunkRepository,
    scope: Scope,
    other_scope: Scope,
) -> None:
    indexer.index(scope, "private.pdf", make_pdf("the secret is 42"))

    assert chunks.list_documents(other_scope) == []


def test_deleting_a_document_only_touches_that_organisations_copy(
    indexer: Indexer,
    chunks: InMemoryChunkRepository,
    scope: Scope,
    other_scope: Scope,
) -> None:
    pdf = make_pdf("shared file name")
    indexer.index(scope, "notes.pdf", pdf)
    indexer.index(other_scope, "notes.pdf", pdf)

    chunks.delete_document(scope, "notes.pdf")

    assert chunks.list_documents(scope) == []
    assert chunks.list_documents(other_scope) == ["notes.pdf"]
