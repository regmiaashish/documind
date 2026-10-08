"""Document resource routes; ingestion and SQL stay in their own layers."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Path, Query, Response, UploadFile

from documind.core.config import settings
from documind.core.dependencies import Embeddings, Pool, User
from documind.exceptions import AppError
from documind.repositories import documents
from documind.repositories.chunks import get_chunk
from documind.schemas.chat import SourcePassage
from documind.schemas.documents import ChunkSize, Document, UploadResult
from documind.services.ingestion import ingest_document

router = APIRouter(prefix="/documents", tags=["documents"])
DEFAULT_CHUNK_SIZE = ChunkSize(settings.chunk_size)


@router.post("", response_model=UploadResult, status_code=201)
async def upload_document(
    response: Response,
    pool: Pool,
    user_id: User,
    embeddings: Embeddings,
    file: Annotated[UploadFile, File()],
    chunk_size: Annotated[ChunkSize, Query()] = DEFAULT_CHUNK_SIZE,
) -> UploadResult:
    """doc-mind-ai: upload PDF/text; return 200 for an existing document, otherwise 201."""
    try:
        data = await file.read(settings.max_upload_bytes + 1)
        result = await ingest_document(
            pool,
            embeddings,
            user_id,
            file.filename,
            file.content_type,
            data,
            chunk_size,
        )
    finally:
        await file.close()
    if result.duplicate:
        response.status_code = 200
    response.headers["Location"] = f"/api/v1/documents/{result.document_id}"
    return result


@router.get("", response_model=list[Document])
async def list_documents(
    pool: Pool,
    user_id: User,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Document]:
    return await documents.list_documents(pool, user_id, limit, offset)


@router.get("/{document_id}", response_model=Document)
async def get_document(document_id: UUID, pool: Pool, user_id: User) -> Document:
    document = await documents.get_document(pool, user_id, document_id)
    if document is None:
        raise AppError(404, "document_not_found", "Document not found.")
    return document


@router.get("/{document_id}/chunks/{chunk_index}", response_model=SourcePassage)
async def read_chunk(
    document_id: UUID, chunk_index: Annotated[int, Path(ge=0)], pool: Pool, user_id: User
) -> dict:
    chunk = await get_chunk(pool, user_id, document_id, chunk_index)
    if chunk is None:
        raise AppError(404, "chunk_not_found", "Source passage not found.")
    return chunk


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: UUID, pool: Pool, user_id: User) -> Response:
    if not await documents.delete_document(pool, user_id, document_id):
        raise AppError(404, "document_not_found", "Document not found.")
    return Response(status_code=204)
