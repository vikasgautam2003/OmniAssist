import uuid

from app.domain import Artifact, Scope


class InMemoryArtifactStore:
    def __init__(self) -> None:
        self._rows: dict[uuid.UUID, tuple[tuple[uuid.UUID, uuid.UUID], Artifact]] = {}

    def save(
        self, scope: Scope, filename: str, media_type: str, content: bytes
    ) -> uuid.UUID:
        artifact_id = uuid.uuid4()
        self._rows[artifact_id] = (
            (scope.organisation_id, scope.user_id),
            Artifact(
                id=artifact_id,
                filename=filename,
                media_type=media_type,
                content=content,
            ),
        )
        return artifact_id

    def get(self, scope: Scope, artifact_id: uuid.UUID) -> Artifact | None:
        found = self._rows.get(artifact_id)

        if found is None or found[0] != (scope.organisation_id, scope.user_id):
            return None

        return found[1]
