"""Create one PostgreSQL connection pool per application process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg

from documind.core.config import settings


@asynccontextmanager
async def database_pool() -> AsyncIterator[asyncpg.Pool]:
    pool = await asyncpg.create_pool(str(settings.database_url), min_size=1, max_size=5)
    try:
        yield pool
    finally:
        await pool.close()
