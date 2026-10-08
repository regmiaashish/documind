"""Confirmation locks the draft and creates at most one ticket, in one transaction."""

from uuid import UUID

import asyncpg

from documind.exceptions import AppError
from documind.schemas.tools import CreateTicket, PendingAction, Ticket


async def draft_ticket(pool: asyncpg.Pool, owner: UUID, draft: CreateTicket) -> PendingAction:
    row = await pool.fetchrow(
        "INSERT INTO pending_actions (owner_id, subject, body) VALUES ($1, $2, $3) RETURNING *",
        owner,
        draft.subject,
        draft.body,
    )
    return PendingAction(**dict(row))


async def confirm_ticket(pool: asyncpg.Pool, owner: UUID, action_id: UUID) -> Ticket:
    async with pool.acquire() as connection, connection.transaction():
        action = await connection.fetchrow(
            "SELECT *, expires_at > now() AS valid FROM pending_actions WHERE id=$1 AND owner_id=$2 FOR UPDATE",
            action_id,
            owner,
        )
        if action is None:
            raise AppError(404, "action_not_found", "Ticket draft not found.")
        existing = await connection.fetchrow(
            "SELECT * FROM tickets WHERE action_id=$1 AND owner_id=$2", action_id, owner
        )
        if existing:
            return Ticket(**dict(existing))
        if not action["valid"]:
            raise AppError(409, "action_expired", "This draft expired. Ask for a new ticket draft.")
        row = await connection.fetchrow(
            "INSERT INTO tickets (action_id, owner_id, subject, body) VALUES ($1,$2,$3,$4) RETURNING *",
            action_id,
            owner,
            action["subject"],
            action["body"],
        )
        return Ticket(**dict(row))
