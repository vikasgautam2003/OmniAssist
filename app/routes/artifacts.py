import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.artifacts.postgres import PostgresArtifactStore
from app.routes.deps import CurrentUser

router = APIRouter()


@router.get("/artifacts/{artifact_id}")
def download(artifact_id: uuid.UUID, user: CurrentUser) -> Response:
    artifact = PostgresArtifactStore().get(user.id, artifact_id)

    if artifact is None:
        # 404 whether it does not exist or belongs to someone else: 403 would
        # confirm the id is real, which is the whole of what an attacker needs.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")

    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            # The filename is already whitelisted at creation; quoting it here
            # is the second line against header injection.
            "Content-Disposition": f'attachment; filename="{artifact.filename}"'
        },
    )
