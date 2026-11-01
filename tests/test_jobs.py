import uuid

import pytest

from app.jobs import indexing


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    """Replace every real dependency of the job with a fake."""
    state: dict[str, object] = {}

    class FakeArtifact:
        filename = "policy.pdf"
        content = b"%PDF-fake"

    class FakeStore:
        def get(self, user_id: uuid.UUID, artifact_id: uuid.UUID) -> object | None:
            return FakeArtifact() if state.get("exists", True) else None

    class FakeIndexer:
        def __init__(self, *args: object, **kwargs: object) -> None: ...

        def index(self, user_id: uuid.UUID, name: str, data: bytes) -> int:
            if state.get("raise"):
                raise indexing.PdfExtractionError("No text could be extracted.")
            state["indexed"] = name
            return 7

    monkeypatch.setattr(indexing, "PostgresArtifactStore", FakeStore)
    monkeypatch.setattr(indexing, "Indexer", FakeIndexer)

    class FakeSettings:
        chunk_size = 1000
        chunk_overlap = 150

    monkeypatch.setattr(indexing, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(indexing, "get_embedder", lambda: object())
    monkeypatch.setattr(indexing, "PostgresChunkRepository", lambda: object())
    return state


def test_a_queued_document_is_indexed(stored: dict[str, object]) -> None:
    result = indexing.index_uploaded_document(uuid.uuid4(), uuid.uuid4())

    assert result == {"status": "done", "document_name": "policy.pdf", "passages": 7}


def test_a_bad_pdf_is_reported_not_retried(stored: dict[str, object]) -> None:
    """Retrying cannot help a scanned document, and the message says why."""
    stored["raise"] = True

    result = indexing.index_uploaded_document(uuid.uuid4(), uuid.uuid4())

    assert result["status"] == "failed"
    assert "No text" in str(result["error"])


def test_the_job_checks_ownership_too(stored: dict[str, object]) -> None:
    """Task arguments travel through a broker, so a task must not trust them
    any more than a request does."""
    stored["exists"] = False

    result = indexing.index_uploaded_document(uuid.uuid4(), uuid.uuid4())

    assert result["status"] == "failed"
    assert "not be found" in str(result["error"])


def test_the_task_is_a_thin_wrapper() -> None:
    """The work is a plain function so it can be tested with no broker, no
    worker and no Redis running at all."""
    assert indexing.index_uploaded_document_task.name == "index_uploaded_document"


def test_importing_the_celery_app_needs_no_configuration() -> None:
    """Celery binds its broker at import, before any .env is required. If that
    import demanded Settings, CI could not import the app without secrets --
    the invariant the whole interface design exists to protect."""
    import importlib
    import os

    from app.jobs import celery_app as module

    saved = {
        k: os.environ.pop(k)
        for k in list(os.environ)
        if k.startswith(("DATABASE_", "JWT_", "LLM_"))
    }
    try:
        importlib.reload(module)
        assert module.celery_app.conf.broker_url
    finally:
        os.environ.update(saved)


def test_the_redis_default_cannot_drift() -> None:
    from app.config import Settings
    from app.jobs.celery_app import DEFAULT_REDIS_URL

    assert Settings.model_fields["redis_url"].default == DEFAULT_REDIS_URL
