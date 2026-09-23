import json
from collections.abc import Iterator
from functools import lru_cache

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.clients.factory import get_llm_client
from app.services.chat import ChatService

router = APIRouter()


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    """One shared service for the process, built on first request.

    Cached so conversation history survives between requests; lazy so that
    importing this module requires no credentials.
    """
    return ChatService(get_llm_client())


class ChatRequest(BaseModel):
    message: str


def _to_sse(chunks: Iterator[str]) -> Iterator[str]:
    for chunk in chunks:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/{conversation_id}")
def chat(conversation_id: str, request: ChatRequest) -> StreamingResponse:
    stream = get_chat_service().stream_reply(conversation_id, request.message)
    return StreamingResponse(
        _to_sse(stream),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
