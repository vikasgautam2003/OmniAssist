import time
import uuid

from app.artifacts.postgres import PostgresArtifactStore
from app.config import get_settings
from app.embeddings.factory import get_embedder
from app.jobs.celery_app import celery_app
from app.observability.logging import get_logger, new_request
from app.repositories.postgres import PostgresChunkRepository
from app.services.indexing import Indexer
from app.services.pdf import PdfExtractionError

logger = get_logger("jobs")


def index_uploaded_document(
    user_id: uuid.UUID, artifact_id: uuid.UUID
) -> dict[str, object]:
    """Index a previously stored upload. Plain function on purpose.

    The Celery task below is a thin wrapper around this, so the work can be
    tested without a broker, a worker or Redis running at all.
    """
    # A job has no HTTP request to inherit a correlation id from, so it
    # starts its own scope -- otherwise its lines float free of any context.
    new_request(user_id)
    started = time.perf_counter()

    artifact = PostgresArtifactStore().get(user_id, artifact_id)

    if artifact is None:
        # Ownership is checked here too: the task arguments travel through a
        # broker, and a task must not trust them any more than a request does.
        logger.warning(
            "index.rejected", reason="not_found", artifact_id=str(artifact_id)
        )
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
        logger.info(
            "index.failed",
            document=artifact.filename,
            reason="unreadable",
            duration_ms=round((time.perf_counter() - started) * 1000, 1),
        )
        return {"status": "failed", "error": str(exc)}

    logger.info(
        "index.done",
        document=artifact.filename,
        passages=passages,
        bytes=len(artifact.content),
        duration_ms=round((time.perf_counter() - started) * 1000, 1),
    )

    return {
        "status": "done",
        "document_name": artifact.filename,
        "passages": passages,
    }


@celery_app.task(name="index_uploaded_document")
def index_uploaded_document_task(user_id: str, artifact_id: str) -> dict[str, object]:
    return index_uploaded_document(uuid.UUID(user_id), uuid.UUID(artifact_id))
