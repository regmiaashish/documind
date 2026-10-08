"""Saved evidence and explicit human review fields; no automatic semantic grading."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from documind.schemas.chat import ChatAnswer, RetrievalMode, RetrievedChunk

MODES: tuple[RetrievalMode, ...] = ("vector", "hybrid", "hybrid_rerank")
SIZES = (300, 800)


class Question(BaseModel):
    id: str
    question: str
    expected_answer: str
    section: str | None
    page: int | None = None
    evidence: list[str] = Field(default_factory=list)
    expected_refusal: bool = False


class Result(BaseModel):
    case: Question
    chunk_size: Literal[300, 800]
    retrieval_mode: RetrievalMode
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    answer: ChatAnswer | None = None
    latency_ms: int
    hit_at_5: bool | None = None
    error: str | None = None
    supported: bool | None = None
    correct: bool | None = None
    review_notes: str = ""


class EvaluationRun(BaseModel):
    started_at: datetime
    document_sha256: str
    questions_sha256: str
    configuration: dict
    results: list[Result] = Field(default_factory=list)
