"""Route chat requests and keep errors consistent across JSON and SSE."""

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.exceptions import AppError
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM
from documind.schemas.chat import ChatRequest
from documind.services.agent import agent_events
from documind.services.rag import answer_events
from documind.services.router import needs_tools

logger = logging.getLogger(__name__)


async def guarded_events(
    pool: asyncpg.Pool,
    embeddings: GeminiEmbeddings,
    llm: GeminiLLM,
    owner_id: UUID,
    request: ChatRequest,
) -> AsyncIterator[tuple[str, dict]]:
    try:
        async with asyncio.timeout(settings.request_timeout_seconds):
            events = (
                agent_events(pool, embeddings, llm, owner_id, request)
                if needs_tools(request.question)
                else answer_events(pool, embeddings, llm, owner_id, request)
            )
            async for event in events:
                yield event
    except AppError as error:
        yield "error", {"code": error.code, "message": error.message, "status": error.status}
    except TimeoutError:
        yield (
            "error",
            {"code": "answer_timeout", "message": "The answer took too long. Please retry."},
        )
    except (asyncpg.PostgresError, OSError):
        yield (
            "error",
            {
                "code": "retrieval_unavailable",
                "message": "Document search is unavailable. Please retry.",
            },
        )
    except Exception:
        logger.exception("Unexpected answer failure")
        yield "error", {"code": "internal_error", "message": "The answer failed. Please retry."}
    yield "done", {}
