import json
from collections.abc import Iterator
from functools import lru_cache

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.artifacts.postgres import PostgresArtifactStore
from app.clients.factory import get_llm_client
from app.config import get_settings
from app.embeddings.factory import get_embedder
from app.repositories.base import ConversationNotFoundError
from app.repositories.postgres import (
    PostgresChunkRepository,
    PostgresConversationRepository,
)
from app.routes.deps import CurrentPrincipal
from app.services.chat import ChatService
from app.services.retrieval import Retriever
from app.tools.calculator import Calculator
from app.tools.charts import CreateChart
from app.tools.documents import CreateDocument
from app.tools.registry import ToolRegistry
from app.tools.spreadsheets import CreateSpreadsheet

router = APIRouter()


@lru_cache(maxsize=1)
def get_chat_service() -> ChatService:
    """One shared service for the process, built on first request.

    Cached so conversation history survives between requests; lazy so that
    importing this module requires no credentials.
    """
    retriever = Retriever(
        get_embedder(),
        PostgresChunkRepository(),
        top_k=get_settings().retrieval_top_k,
    )
    settings = get_settings()
    artifacts = PostgresArtifactStore()
    return ChatService(
        get_llm_client(),
        PostgresConversationRepository(),
        retriever=retriever,
        tools=ToolRegistry(
            [
                Calculator(),
                CreateDocument(artifacts),
                CreateSpreadsheet(artifacts),
                CreateChart(artifacts),
            ]
        ),
        max_tool_iterations=settings.max_tool_iterations,
    )


class ChatRequest(BaseModel):
    message: str


def _to_sse(chunks: Iterator[str]) -> Iterator[str]:
    for chunk in chunks:
        yield f"data: {json.dumps(chunk)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/chat/{conversation_id}")
def chat(
    conversation_id: str, request: ChatRequest, principal: CurrentPrincipal
) -> StreamingResponse:
    try:
        stream = get_chat_service().stream_reply(
            conversation_id, principal.scope(), request.message
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
