"""Only validated arguments enter tools; ownership always comes from authentication."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, TypeAdapter


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchDocs(ToolArguments):
    tool: Literal["search_docs"]
    question: str = Field(min_length=1, max_length=2000)


class GetOrderStatus(ToolArguments):
    tool: Literal["get_order_status"]
    order_id: str = Field(pattern=r"^ORD-\d{4,10}$")


class CreateTicket(ToolArguments):
    tool: Literal["create_ticket"]
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=2000)


tool_arguments = TypeAdapter(
    Annotated[SearchDocs | GetOrderStatus | CreateTicket, Field(discriminator="tool")]
)


class OrderBatch(ToolArguments):
    calls: list[GetOrderStatus] = Field(min_length=2, max_length=3)


class PendingAction(BaseModel):
    id: UUID
    subject: str
    body: str
    expires_at: AwareDatetime


class Ticket(BaseModel):
    id: UUID
    subject: str
    body: str
    created_at: AwareDatetime
