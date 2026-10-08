"""Duplicate and failed uploads must avoid unnecessary work or partial records."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from documind.exceptions import AppError
from documind.schemas.documents import Document
from documind.services.ingestion import ingest_document

OWNER = UUID(int=1)


def document():
    return Document(
        document_id=UUID(int=10),
        filename="policy.txt",
        content_type="text/plain",
        size_bytes=20,
        page_count=None,
        chunk_count=1,
        chunk_size=300,
        chunk_overlap=50,
        embedding_model="gemini-embedding-2",
        created_at=datetime.now(UTC),
    )


async def test_duplicate_skips_provider_and_insert(monkeypatch):
    async def find(*args):
        return document()

    monkeypatch.setattr("documind.services.ingestion.find_duplicate", find)
    result = await ingest_document(
        None, None, OWNER, "policy.txt", "text/plain", b"existing policy", 300
    )
    assert result.duplicate and result.document_id == UUID(int=10)


async def test_provider_failure_does_not_persist(monkeypatch):
    async def find(*args):
        return None

    async def save(*args):
        raise AssertionError("Failed embeddings must not reach persistence")

    class FailedEmbeddings:
        async def embed_documents(self, texts, title):
            raise AppError(503, "embedding_unavailable", "Retry later.")

    monkeypatch.setattr("documind.services.ingestion.find_duplicate", find)
    monkeypatch.setattr("documind.services.ingestion.save_document", save)
    with pytest.raises(AppError, match="Retry later"):
        await ingest_document(
            None, FailedEmbeddings(), OWNER, "policy.txt", "text/plain", b"policy", 300
        )


async def test_success_passes_owner_chunks_and_embeddings_to_storage(monkeypatch):
    async def find(*args):
        return None

    class Embeddings:
        async def embed_documents(self, texts, title):
            assert title == "policy.txt" and texts == ["20 days annual leave"]
            return [[1.0] + [0.0] * 767]

    async def save(pool, owner, name, mime, size, digest, pages, chunk_size, chunks, vectors):
        assert owner == OWNER and pages is None
        assert len(digest) == 64 and len(chunks) == len(vectors) == 1
        assert chunks[0].content == "20 days annual leave"
        return document(), False

    monkeypatch.setattr("documind.services.ingestion.find_duplicate", find)
    monkeypatch.setattr("documind.services.ingestion.save_document", save)
    result = await ingest_document(
        None, Embeddings(), OWNER, "policy.txt", "text/plain", b"20 days annual leave", 300
    )
    assert not result.duplicate
