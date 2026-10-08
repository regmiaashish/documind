"""Retrieval always joins owner-scoped documents, including keyword search."""

import re
from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.schemas.chat import ChatRequest, RetrievedChunk

ELIGIBLE = """FROM chunks c JOIN documents d ON d.id = c.document_id
    WHERE d.owner_id = $1
      AND ($2::uuid[] IS NULL OR d.id = ANY($2::uuid[]))
      AND ($3::timestamptz IS NULL OR d.created_at >= $3)
      AND ($4::timestamptz IS NULL OR d.created_at <= $4)
      AND d.embedding_model = $5 AND d.chunk_size = $6"""
COLUMNS = """c.id AS chunk_id, c.document_id, d.filename, c.chunk_index, c.page, c.content,
    1 - (c.embedding <=> $7::vector) AS similarity"""


QUESTION_WORDS = {
    "what",
    "which",
    "who",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "much",
    "many",
    "please",
    "tell",
}


def keyword_query(question: str) -> str:
    """Remove question framing; PostgreSQL still handles stemming and stop words."""
    return " ".join(
        term
        for term in re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", question.lower())
        if term not in QUESTION_WORDS
    )


async def search_chunks(
    pool: asyncpg.Pool,
    owner_id: UUID,
    request: ChatRequest,
    vector: list[float],
    keyword: bool = False,
) -> list[RetrievedChunk]:
    # All interpolated SQL fragments are fixed program text; values use parameters.
    if keyword:
        query = keyword_query(request.question)
        if not query:
            return []
        # PostgreSQL full-text search stems words and removes stop words. Generic
        # substrings (e.g. "who" inside "whole") must not become lexical evidence.
        sql = f"""SELECT {COLUMNS}, true AS keyword_match {ELIGIBLE}
            AND c.tsv @@ plainto_tsquery('english', $8)
            ORDER BY ts_rank_cd(c.tsv, plainto_tsquery('english', $8)) DESC, c.id
            LIMIT $9"""
        extra = [query, settings.retrieval_candidates]
    else:
        sql = f"""SELECT {COLUMNS}, false AS keyword_match {ELIGIBLE}
            ORDER BY c.embedding <=> $7::vector, c.id LIMIT $8"""
        extra = [settings.retrieval_candidates]
    rows = await pool.fetch(
        sql,
        owner_id,
        request.document_ids,
        request.created_after,
        request.created_before,
        settings.embedding_model,
        int(request.chunk_size),
        str(vector),
        *extra,
    )
    return [RetrievedChunk(**dict(row)) for row in rows]


async def get_chunk(
    pool: asyncpg.Pool, owner_id: UUID, document_id: UUID, chunk_index: int
) -> dict | None:
    row = await pool.fetchrow(
        """SELECT c.document_id, d.filename, c.chunk_index, c.page, c.content
           FROM chunks c JOIN documents d ON d.id = c.document_id
           WHERE d.owner_id = $1 AND d.id = $2 AND c.chunk_index = $3""",
        owner_id,
        document_id,
        chunk_index,
    )
    return dict(row) if row else None


async def summary_chunks(
    pool: asyncpg.Pool, owner_id: UUID, request: ChatRequest
) -> list[RetrievedChunk]:
    rows = await pool.fetch(
        f"""SELECT c.id AS chunk_id, c.document_id, d.filename, c.chunk_index, c.page,
            c.content, 0.0 AS similarity {ELIGIBLE}
            ORDER BY d.id, c.chunk_index LIMIT $7""",
        owner_id,
        request.document_ids,
        request.created_after,
        request.created_before,
        settings.embedding_model,
        int(request.chunk_size),
        settings.max_chunks,
    )
    return [RetrievedChunk(**dict(row)) for row in rows]
