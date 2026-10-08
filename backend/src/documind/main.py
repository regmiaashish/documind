"""Application startup and infrastructure readiness."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from documind.api.actions import router as actions_router
from documind.api.chat import router as chat_router
from documind.api.documents import router as documents_router
from documind.api.health import router as health_router
from documind.core.config import settings
from documind.core.db import database_pool
from documind.core.rate_limit import limiter, rate_limit_error
from documind.exceptions.handlers import register_handlers
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with database_pool() as pool, httpx.AsyncClient() as client:
        app.state.pool = pool
        app.state.embeddings = GeminiEmbeddings(
            client, settings.gemini_api_key.get_secret_value().strip()
        )
        app.state.llm = GeminiLLM(client, settings.gemini_api_key.get_secret_value().strip())
        yield


app = FastAPI(title="DocuMind", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_error)


app.include_router(health_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")
app.include_router(actions_router, prefix="/api/v1")
register_handlers(app)
