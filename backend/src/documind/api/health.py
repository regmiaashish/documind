"""Database readiness endpoint."""

import asyncpg
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=None)
async def health(request: Request) -> dict[str, str] | JSONResponse:
    """Report readiness only when the migrated schema is available."""
    try:
        async with request.app.state.pool.acquire(timeout=3) as connection:
            await connection.fetchval("SELECT id FROM users LIMIT 1", timeout=3)
    except (asyncpg.PostgresError, OSError, TimeoutError):
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return {"status": "ok"}
