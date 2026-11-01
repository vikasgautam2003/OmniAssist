import uuid
from typing import Protocol

from app.domain import Artifact


class ArtifactStore(Protocol):
    def save(
        self, user_id: uuid.UUID, filename: str, media_type: str, content: bytes
    ) -> uuid.UUID: ...

    def get(self, user_id: uuid.UUID, artifact_id: uuid.UUID) -> Artifact | None: ...
