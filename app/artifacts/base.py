import uuid
from typing import Protocol

from app.domain import Artifact, Scope


class ArtifactStore(Protocol):
    def save(
        self, scope: Scope, filename: str, media_type: str, content: bytes
    ) -> uuid.UUID: ...

    def get(self, scope: Scope, artifact_id: uuid.UUID) -> Artifact | None: ...
