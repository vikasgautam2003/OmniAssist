from functools import lru_cache

from app.config import get_settings
from app.embeddings.base import Embedder


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Build the configured embedder once per process."""
    provider = get_settings().embedding_provider

    if provider == "local":
        from app.embeddings.local import LocalEmbedder

        return LocalEmbedder()

    raise NotImplementedError(
        f"Embedding provider {provider!r} is not implemented yet."
    )
