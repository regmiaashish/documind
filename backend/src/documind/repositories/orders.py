"""Order reads use the same authenticated owner boundary as document reads."""

from uuid import UUID

import asyncpg


async def get_order_status(pool: asyncpg.Pool, owner: UUID, order_id: str) -> dict | None:
    row = await pool.fetchrow(
        "SELECT id, status, delivery_date FROM orders WHERE id=$1 AND owner_id=$2", order_id, owner
    )
    return dict(row) if row else None
