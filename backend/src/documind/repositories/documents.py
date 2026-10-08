"""Owner-scoped reads and atomic document/chunk insertion."""

from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.schemas.documents import Chunk, Document

COLUMNS = """id AS document_id, filename, content_type, size_bytes, page_count,
             chunk_count, chunk_size, chunk_overlap, embedding_model, created_at"""


async def find_duplicate(
    pool: asyncpg.Pool, owner_id: UUID, content_hash: str, chunk_size: int
) -> Document | None:
    row = await pool.fetchrow(
        f"""SELECT {COLUMNS} FROM documents
            WHERE owner_id = $1 AND content_hash = $2 AND chunk_size = $3
              AND chunk_overlap = $4 AND embedding_model = $5""",
        owner_id,
        content_hash,
        chunk_size,
        settings.chunk_overlap,
        settings.embedding_model,
    )
    return Document(**dict(row)) if row else None


async def get_document(pool: asyncpg.Pool, owner_id: UUID, document_id: UUID) -> Document | None:
    row = await pool.fetchrow(
        f"SELECT {COLUMNS} FROM documents WHERE owner_id = $1 AND id = $2", owner_id, document_id
    )
    return Document(**dict(row)) if row else None


async def list_documents(
    pool: asyncpg.Pool, owner_id: UUID, limit: int, offset: int
) -> list[Document]:
    rows = await pool.fetch(
        f"""SELECT {COLUMNS} FROM documents WHERE owner_id = $1
            ORDER BY created_at DESC, id DESC LIMIT $2 OFFSET $3""",
        owner_id,
        limit,
        offset,
    )
    return [Document(**dict(row)) for row in rows]


async def delete_document(pool: asyncpg.Pool, owner_id: UUID, document_id: UUID) -> bool:
    deleted = await pool.fetchval(
        "DELETE FROM documents WHERE owner_id = $1 AND id = $2 RETURNING id",
        owner_id,
        document_id,
    )
    return deleted is not None


async def save_document(
    pool: asyncpg.Pool,
    owner_id: UUID,
    filename: str,
    content_type: str,
    size_bytes: int,
    content_hash: str,
    page_count: int | None,
    chunk_size: int,
    chunks: list[Chunk],
    vectors: list[list[float]],
) -> tuple[Document, bool]:
    async with pool.acquire() as connection, connection.transaction():
        row = await connection.fetchrow(
            f"""INSERT INTO documents
                (owner_id, filename, content_type, size_bytes, content_hash, page_count,
                 chunk_count, chunk_size, chunk_overlap, embedding_model)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (owner_id,content_hash,chunk_size,chunk_overlap,embedding_model)
                DO NOTHING RETURNING {COLUMNS}""",
            owner_id,
            filename,
            content_type,
            size_bytes,
            content_hash,
            page_count,
            len(chunks),
            chunk_size,
            settings.chunk_overlap,
            settings.embedding_model,
        )
        if row is None:
            # A concurrent upload may have committed after our initial duplicate check.
            row = await connection.fetchrow(
                f"""SELECT {COLUMNS} FROM documents
                    WHERE owner_id=$1 AND content_hash=$2 AND chunk_size=$3
                      AND chunk_overlap=$4 AND embedding_model=$5""",
                owner_id,
                content_hash,
                chunk_size,
                settings.chunk_overlap,
                settings.embedding_model,
            )
            return Document(**dict(row)), True
        await connection.executemany(
            """INSERT INTO chunks (document_id, chunk_index, page, content, token_count, embedding)
               VALUES ($1,$2,$3,$4,$5,$6::vector)""",
            [
                (
                    row["document_id"],
                    index,
                    chunk.page,
                    chunk.content,
                    chunk.token_count,
                    str(vector),
                )
                for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
            ],
        )
        return Document(**dict(row)), False
