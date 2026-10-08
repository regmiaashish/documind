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


async def search_chunks(
    pool: asyncpg.Pool,
    owner_id: UUID,
    request: ChatRequest,
    vector: list[float],
    keyword: bool = False,
) -> list[RetrievedChunk]:
    # All interpolated SQL fragments are fixed program text; values use parameters.
    if keyword:
        terms = [term for term in re.findall(r"[A-Za-z0-9]+", request.question) if len(term) > 2]
        patterns = [f"%{term}%" for term in terms]
        sql = f"""SELECT {COLUMNS}, true AS keyword_match {ELIGIBLE}
            AND (c.tsv @@ websearch_to_tsquery('english', $9)
                 OR c.content ILIKE ANY($8::text[]))
            ORDER BY ts_rank_cd(c.tsv, websearch_to_tsquery('english', $9)) DESC, c.id
            LIMIT $10"""
        extra = [patterns, request.question, settings.retrieval_candidates]
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
