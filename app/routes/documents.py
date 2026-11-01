from functools import lru_cache
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.artifacts.postgres import PostgresArtifactStore
from app.config import get_settings
from app.jobs.celery_app import celery_app
from app.jobs.indexing import index_uploaded_document_task
from app.repositories.postgres import PostgresChunkRepository
from app.routes.deps import CurrentUser

router = APIRouter()

PDF_MEDIA_TYPE = "application/pdf"


@lru_cache(maxsize=1)
def get_artifacts() -> PostgresArtifactStore:
    return PostgresArtifactStore()


class UploadAccepted(BaseModel):
    job_id: str
    document_name: str


class JobStatus(BaseModel):
    job_id: str
    state: str
    result: dict[str, Any] | None = None


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
async def upload(user: CurrentUser, file: UploadFile) -> UploadAccepted:
    """Accept an upload and queue it for indexing.

    202, not 201: the work has not happened yet. Indexing a long PDF embeds
    hundreds of passages, which held a worker for the whole request and gave
    the user a spinner with no way to know whether it was progressing.
    """
    limit = get_settings().max_upload_bytes

    # Checked before reading. Reading first would let one large request
    # exhaust memory, which is a denial of service needing no skill.
    if file.size is not None and file.size > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File is larger than the {limit // 1_000_000} MB limit.",
        )

    data = await file.read()

    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File is larger than the {limit // 1_000_000} MB limit.",
        )

    name = file.filename or "document.pdf"

    # The bytes are stored first and only an id is queued. Putting megabytes
    # through the broker would make Redis a file store, which it is not: its
    # payloads are held in memory and it has no durability guarantee worth
    # betting a user's upload on.
    artifact_id = get_artifacts().save(user.id, name, PDF_MEDIA_TYPE, data)

    task = index_uploaded_document_task.delay(str(user.id), str(artifact_id))

    return UploadAccepted(job_id=task.id, document_name=name)


@router.get("/documents/jobs/{job_id}")
def job_status(job_id: str, user: CurrentUser) -> JobStatus:
    """Report on a queued indexing job.

    Celery states: PENDING, STARTED, SUCCESS, FAILURE. PENDING also means
    "unknown id", because a broker remembers nothing it was never told --
    so this cannot distinguish a queued job from a fictional one.
    """
    result = celery_app.AsyncResult(job_id)
    payload = result.result if result.successful() else None

    return JobStatus(
        job_id=job_id,
        state=result.state,
        result=payload if isinstance(payload, dict) else None,
    )


@router.get("/documents")
def list_documents(user: CurrentUser) -> list[str]:
    return PostgresChunkRepository().list_documents(user.id)
