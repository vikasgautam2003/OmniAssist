import uuid

from sqlalchemy import select

from app.db.models import ArtifactRow
from app.db.session import get_session_factory
from app.domain import Artifact, Scope


class PostgresArtifactStore:
    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def save(
        self, scope: Scope, filename: str, media_type: str, content: bytes
    ) -> uuid.UUID:
        row = ArtifactRow(
            organisation_id=scope.organisation_id,
            user_id=scope.user_id,
            filename=filename,
            media_type=media_type,
            content=content,
        )

        with self._session_factory() as session:
            session.add(row)
            session.commit()
            return row.id

    def get(self, scope: Scope, artifact_id: uuid.UUID) -> Artifact | None:
        # Ownership is in the query, as everywhere else: a download URL is
        # guessable in principle, and must not be enough on its own.
        query = select(ArtifactRow).where(
            ArtifactRow.id == artifact_id,
            ArtifactRow.organisation_id == scope.organisation_id,
            ArtifactRow.user_id == scope.user_id,
        )

        with self._session_factory() as session:
            row = session.scalar(query)

        if row is None:
            return None

        return Artifact(
            id=row.id,
            filename=row.filename,
            media_type=row.media_type,
            content=row.content,
        )
