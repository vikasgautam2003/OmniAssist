from functools import lru_cache

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.config import get_settings
from app.embeddings.base import EmbeddingError
from app.embeddings.factory import get_embedder
from app.repositories.postgres import PostgresChunkRepository
from app.routes.deps import CurrentUser
from app.services.indexing import Indexer
from app.services.pdf import PdfExtractionError

router = APIRouter()


@lru_cache(maxsize=1)
def get_indexer() -> Indexer:
    settings = get_settings()
    return Indexer(
        get_embedder(),
        PostgresChunkRepository(),
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )


class UploadResponse(BaseModel):
    document_name: str
    passages: int


@router.post("/documents", status_code=status.HTTP_201_CREATED)
async def upload(user: CurrentUser, file: UploadFile) -> UploadResponse:
    limit = get_settings().max_upload_bytes

    # Checked before reading. Reading first would mean a single large request
    # could exhaust memory, which is a denial of service needing no skill.
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

    try:
        passages = get_indexer().index(user.id, name, data)
    except PdfExtractionError as exc:
        # This message was written for the user -- it names the problem and
        # what to do about it -- so it is safe to pass straight through.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except EmbeddingError as exc:
        # This one is ours, not theirs, and may carry backend detail.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "The document could not be indexed right now. Please try again.",
        ) from exc

    return UploadResponse(document_name=name, passages=passages)


@router.get("/documents")
def list_documents(user: CurrentUser) -> list[str]:
    return PostgresChunkRepository().list_documents(user.id)
