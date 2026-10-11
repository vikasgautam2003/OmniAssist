from typing import Protocol

Vector = list[float]


class EmbeddingError(Exception):
    """Raised when an embedding backend fails or returns an unusable result."""


class Embedder(Protocol):
    @property
    def model_id(self) -> str: ...

    @property
    def dimensions(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[Vector]: ...

    def embed_query(self, text: str) -> Vector: ...
