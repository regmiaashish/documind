"""An unmigrated database must not make the API appear ready."""

from contextlib import asynccontextmanager
from types import SimpleNamespace

import asyncpg
import pytest

from documind.api.health import health


@pytest.mark.parametrize("migrated", [True, False])
async def test_health_requires_migrated_schema(migrated):
    class Connection:
        async def fetchval(self, query, timeout):
            if not migrated:
                raise asyncpg.UndefinedTableError('relation "users" does not exist')

    class Pool:
        @asynccontextmanager
        async def acquire(self, timeout):
            yield Connection()

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(pool=Pool())))
    result = await health(request)
    if migrated:
        assert result == {"status": "ok"}
    else:
        assert result.status_code == 503
        assert result.body == b'{"status":"unavailable"}'
