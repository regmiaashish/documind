"""The browser confirms an exact stored draft; the model cannot confirm it."""

from uuid import UUID

from fastapi import APIRouter

from documind.core.dependencies import Pool, User
from documind.repositories.actions import confirm_ticket
from documind.schemas.tools import Ticket

router = APIRouter(prefix="/actions", tags=["actions"])


@router.post("/{action_id}/confirmation", response_model=Ticket)
async def create_confirmation(action_id: UUID, pool: Pool, user_id: User) -> Ticket:
    return await confirm_ticket(pool, user_id, action_id)
