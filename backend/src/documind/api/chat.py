"""Create an answer resource as JSON or JSON events over SSE."""

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from documind.core.dependencies import LLM, Embeddings, Pool, User
from documind.core.rate_limit import limiter
from documind.exceptions import AppError
from documind.schemas.chat import ChatAnswer, ChatRequest
from documind.services.chat import guarded_events

router = APIRouter(prefix="/chat-messages", tags=["chat"])


@router.post("", response_model=ChatAnswer, responses={200: {"content": {"text/event-stream": {}}}})
@limiter.limit("5/minute")
async def create_message(
    request: Request, body: ChatRequest, pool: Pool, user_id: User, embeddings: Embeddings, llm: LLM
) -> StreamingResponse | ChatAnswer:
    events = guarded_events(pool, embeddings, llm, user_id, body)
    if body.stream:

        async def stream() -> AsyncIterator[str]:
            async for event, data in events:
                yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    answer = None
    async for event, data in events:
        if event == "error":
            raise AppError(data.get("status", 503), data["code"], data["message"])
        if event == "answer":
            answer = ChatAnswer(**data)
    if answer is not None:
        return answer
    raise AppError(503, "empty_answer", "No answer received. Please retry.")
