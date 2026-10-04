import json
from collections.abc import Iterator
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.clients.factory import get_llm_client
from app.repositories.base import ConversationNotFoundError
from app.repositories.postgres import PostgresConversationRepository
from app.routes.deps import CurrentUser
from app.services.chat import ChatService

router = APIRouter()


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    """One shared service for the process, built on first request.

    Cached so conversation history survives between requests; lazy so that
    importing this module requires no credentials.
    """
    return ChatService(get_llm_client(), PostgresConversationRepository())


class ChatRequest(BaseModel):
    message: str


def _to_sse(chunks: Iterator[str]) -> Iterator[str]:
    for chunk in chunks:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/{conversation_id}")
def chat(
    conversation_id: str, request: ChatRequest, user: CurrentUser
) -> StreamingResponse:
    try:
        stream = get_chat_service().stream_reply(
            conversation_id, user.id, request.message
        )
    except ConversationNotFoundError as exc:
        # 404 rather than 403: telling the caller that a conversation exists
        # but is not theirs would let ids be enumerated.
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "Conversation not found"
        ) from exc
    return StreamingResponse(
        _to_sse(stream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
