"""FastAPI dependencies for database access and bearer-token authentication."""

import hashlib
from typing import Annotated
from uuid import UUID

import asyncpg
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from documind.exceptions import AppError
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM
from documind.repositories.users import find_user

bearer = HTTPBearer(auto_error=False)


async def get_pool(request: Request) -> asyncpg.Pool:
    """Inject the existing application pool; do not open a pool per request."""
    return request.app.state.pool


async def get_embeddings(request: Request) -> GeminiEmbeddings:
    return request.app.state.embeddings


async def get_llm(request: Request) -> GeminiLLM:
    return request.app.state.llm


async def get_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    pool: Annotated[asyncpg.Pool, Depends(get_pool)],
) -> UUID:
    if credentials is not None:
        digest = hashlib.sha256(credentials.credentials.encode()).hexdigest()
        user_id = await find_user(pool, digest)
        if user_id is not None:
            request.state.user_id = user_id
            return user_id
    raise AppError(401, "unauthorized", "Provide a valid demo bearer token.")


Pool = Annotated[asyncpg.Pool, Depends(get_pool)]
User = Annotated[UUID, Depends(get_user)]
Embeddings = Annotated[GeminiEmbeddings, Depends(get_embeddings)]
LLM = Annotated[GeminiLLM, Depends(get_llm)]
