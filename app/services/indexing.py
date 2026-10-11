import uuid

from app.embeddings.base import Embedder
from app.repositories.base import ChunkRepository
from app.services.chunking import chunk_text
from app.services.pdf import extract_text


class Indexer:
    """Turns an uploaded PDF into retrievable, embedded passages.

    The write-side mirror of Retriever. Composes extraction, chunking and
    embedding; owns no logic of its own beyond the order they run in.
    """

    def __init__(
        self,
        embedder: Embedder,
        chunks: ChunkRepository,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        self._embedder = embedder
        self._chunks = chunks
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def index(self, user_id: uuid.UUID, document_name: str, data: bytes) -> int:
        """Index a document and return how many passages were stored.

        Extraction and embedding both happen before anything is written, so a
        failure leaves no half-indexed document behind for retrieval to serve.
        """
        text = extract_text(data)
        passages = chunk_text(text, size=self._chunk_size, overlap=self._chunk_overlap)

        if not passages:
            return 0

        vectors = self._embedder.embed_documents(passages)

        # Replace, never append. Re-uploading the same file would otherwise
        # store every passage twice, and retrieval would spend half its
        # context budget repeating itself.
        self._chunks.delete_document(user_id, document_name)
        self._chunks.add(
            user_id=user_id,
            document_name=document_name,
            chunks=passages,
            vectors=vectors,
            model_id=self._embedder.model_id,
        )
        return len(passages)
