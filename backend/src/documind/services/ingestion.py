"""Validate, parse, chunk, embed, and persist a small document synchronously."""

import asyncio
import hashlib
from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.exceptions import AppError
from documind.integrations.embeddings import GeminiEmbeddings
from documind.repositories.documents import find_duplicate, save_document
from documind.schemas.documents import UploadResult
from documind.services.chunking import chunk_text
from documind.services.parsing import parse_file, validate_file


async def ingest_document(
    pool: asyncpg.Pool,
    embeddings: GeminiEmbeddings,
    owner_id: UUID,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    chunk_size: int,
) -> UploadResult:
    """doc-mind-ai: upload deduplication and ingestion, with no partial writes."""
    name, mime = validate_file(filename, content_type, data)
    digest = hashlib.sha256(data).hexdigest()
    existing = await find_duplicate(pool, owner_id, digest, chunk_size)
    if existing:
        return UploadResult(**existing.model_dump(), duplicate=True)
    pages, page_count = await asyncio.to_thread(parse_file, data, mime)
    chunks = [
        chunk
        for page, text in pages
        for chunk in chunk_text(text, chunk_size, settings.chunk_overlap, page)
    ]
    if len(chunks) > settings.max_chunks:
        raise AppError(413, "too_many_chunks", "Document is too long. Split it into smaller files.")
    try:
        async with asyncio.timeout(120):
            vectors = await embeddings.embed_documents([chunk.content for chunk in chunks], name)
    except TimeoutError as error:
        raise AppError(
            503, "embedding_timeout", "Embedding took too long. Retry a smaller file."
        ) from error
    document, duplicate = await save_document(
        pool, owner_id, name, mime, len(data), digest, page_count, chunk_size, chunks, vectors
    )
    return UploadResult(**document.model_dump(), duplicate=duplicate)
