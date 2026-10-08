"""Stateless chat requests, retrieval evidence, and final cited responses."""

from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, model_validator

from documind.core.config import settings
from documind.schemas.documents import ChunkSize
from documind.schemas.tools import PendingAction

RetrievalMode = Literal["vector", "hybrid", "hybrid_rerank"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = Field(default=None, max_length=20)
    created_after: AwareDatetime | None = None
    created_before: AwareDatetime | None = None
    chunk_size: ChunkSize = ChunkSize(settings.chunk_size)
    retrieval_mode: RetrievalMode | None = None
    stream: bool = False

    @model_validator(mode="after")
    def validate_filters(self) -> Self:
        self.question = self.question.strip()
        if not self.question:
            raise ValueError("Question cannot be blank")
        if self.created_after and self.created_before and self.created_after > self.created_before:
            raise ValueError("created_after must be before created_before")
        return self


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None
    content: str
    similarity: float
    keyword_match: bool = False


class Citation(BaseModel):
    source_id: int
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None
    snippet: str


class ChatAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    refused: bool
    retrieval_mode: RetrievalMode
    model: str | None = None
    latency_ms: int
    route: Literal["rag", "agent"] = "rag"
    confirmation: PendingAction | None = None


class SourcePassage(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    page: int | None
    content: str
