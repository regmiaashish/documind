"""Find seeded demo users by their hashed bearer token."""

from uuid import UUID

import asyncpg


async def find_user(pool: asyncpg.Pool, key_hash: str) -> UUID | None:
    return await pool.fetchval("SELECT id FROM users WHERE api_key_hash = $1", key_hash)
