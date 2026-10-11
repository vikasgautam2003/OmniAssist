from fastembed import TextEmbedding

from app.embeddings.base import EmbeddingError, Vector

MODEL_ID = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class LocalEmbedder:
    """Embeds with a model that runs on this machine, at no per-request cost."""

    def __init__(self) -> None:
        try:
            self._model = TextEmbedding(model_name=MODEL_ID)
        except Exception as exc:
            raise EmbeddingError(
                f"Could not load the embedding model {MODEL_ID}."
            ) from exc

    @property
    def model_id(self) -> str:
        return MODEL_ID

    @property
    def dimensions(self) -> int:
        return DIMENSIONS

    def embed_documents(self, texts: list[str]) -> list[Vector]:
        if not texts:
            return []

        try:
            return [vector.tolist() for vector in self._model.embed(texts)]
        except Exception as exc:
            raise EmbeddingError("The embedding model failed on this batch.") from exc

    def embed_query(self, text: str) -> Vector:
        vectors = self.embed_documents([QUERY_PREFIX + text])

        if not vectors:
            raise EmbeddingError("The embedding model returned nothing for the query.")

        return vectors[0]
