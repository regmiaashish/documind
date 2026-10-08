"""Run Alembic through the existing asyncpg driver."""

import asyncio
import logging

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine

from documind.core.config import settings

URL = str(settings.database_url).replace("postgresql://", "postgresql+asyncpg://", 1)
logger = logging.getLogger("alembic.runtime.migration")


def run_migrations(connection: Connection) -> None:
    # Keep the version table in the active schema, including isolated test schemas.
    schema = connection.exec_driver_sql("SELECT current_schema()").scalar_one()
    context.configure(connection=connection, target_metadata=None, version_table_schema=schema)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(URL, poolclass=pool.NullPool)
    try:
        for attempt in range(10):
            try:
                # The schema lookup also starts a transaction; commit the whole upgrade.
                async with engine.begin() as connection:
                    await connection.run_sync(run_migrations)
                return
            except OperationalError:
                if attempt == 9:
                    raise
                logger.warning(
                    "Database connection not ready during migration (attempt %d/10); retrying in 1s",
                    attempt + 1,
                )
                await asyncio.sleep(1)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        run_migrations(connection)
    else:
        asyncio.run(run_online())
