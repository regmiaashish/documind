"""Document metadata returned by the API."""

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


@dataclass(frozen=True)
class Chunk:
    content: str
    token_count: int
    page: int | None


class ChunkSize(IntEnum):
    SMALL = 300
    LARGE = 800


class Document(BaseModel):
    document_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    chunk_count: int
    chunk_size: int
    chunk_overlap: int
    chunk_unit: Literal["lexical_tokens"] = "lexical_tokens"
    embedding_model: str
    created_at: datetime


class UploadResult(Document):
    duplicate: bool
