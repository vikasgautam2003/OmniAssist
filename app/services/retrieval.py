from app.domain import Chunk, Scope
from app.embeddings.base import Embedder
from app.repositories.base import ChunkRepository


class Retriever:
    """Turns a question into the passages most likely to answer it.

    Its own class rather than two more collaborators on ChatService: this owns
    one job and can be tested without a conversation, a client or a history.
    """

    def __init__(
        self, embedder: Embedder, chunks: ChunkRepository, top_k: int = 4
    ) -> None:
        self._embedder = embedder
        self._chunks = chunks
        self._top_k = top_k

    def find(self, scope: Scope, question: str) -> list[Chunk]:
        if not question.strip():
            return []

        vector = self._embedder.embed_query(question)

        # The scope reaches the WHERE clause: retrieval that is not scoped
        # answers one tenant's question from another tenant's documents.
        return self._chunks.search(scope, vector, limit=self._top_k)
