import uuid

from app.artifacts.postgres import PostgresArtifactStore
from app.config import get_settings
from app.embeddings.factory import get_embedder
from app.jobs.celery_app import celery_app
from app.repositories.postgres import PostgresChunkRepository
from app.services.indexing import Indexer
from app.services.pdf import PdfExtractionError


def index_uploaded_document(
    user_id: uuid.UUID, artifact_id: uuid.UUID
) -> dict[str, object]:
    """Index a previously stored upload. Plain function on purpose.

    The Celery task below is a thin wrapper around this, so the work can be
    tested without a broker, a worker or Redis running at all.
    """
    artifact = PostgresArtifactStore().get(user_id, artifact_id)

    if artifact is None:
        # Ownership is checked here too: the task arguments travel through a
        # broker, and a task must not trust them any more than a request does.
        return {"status": "failed", "error": "That upload could not be found."}

    settings = get_settings()
    indexer = Indexer(
        get_embedder(),
        PostgresChunkRepository(),
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )

    try:
        passages = indexer.index(user_id, artifact.filename, artifact.content)
    except PdfExtractionError as exc:
        # A bad PDF is the user's problem to fix and the message says how, so
        # it is carried back rather than retried: retrying cannot help.
        return {"status": "failed", "error": str(exc)}

    return {
        "status": "done",
        "document_name": artifact.filename,
        "passages": passages,
    }


@celery_app.task(name="index_uploaded_document")
def index_uploaded_document_task(user_id: str, artifact_id: str) -> dict[str, object]:
    return index_uploaded_document(uuid.UUID(user_id), uuid.UUID(artifact_id))
