"""The shared pool closes on normal shutdown and application failure."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from documind.core.config import settings
from documind.core.db import database_pool


@pytest.mark.parametrize("fails", [False, True])
async def test_database_pool_lifecycle(monkeypatch, fails):
    pool = SimpleNamespace(close=AsyncMock())
    create = AsyncMock(return_value=pool)
    monkeypatch.setattr("documind.core.db.asyncpg.create_pool", create)

    async def use_pool():
        async with database_pool() as shared:
            assert shared is pool
            pool.close.assert_not_awaited()
            if fails:
                raise RuntimeError("Application startup failed")

    if fails:
        with pytest.raises(RuntimeError, match="Application startup failed"):
            await use_pool()
    else:
        await use_pool()
    create.assert_awaited_once_with(str(settings.database_url), min_size=1, max_size=5)
    pool.close.assert_awaited_once()
