"""Verify resource status codes, auth, error shapes, and upload settings offline."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
import pytest

from documind.core.dependencies import get_pool, get_user
from documind.exceptions import AppError
from documind.main import app
from documind.schemas.documents import UploadResult


@pytest.fixture
async def client():
    async def pool():
        return None

    async def user():
        return UUID(int=1)

    app.dependency_overrides[get_pool] = pool
    app.dependency_overrides[get_user] = user
    app.state.embeddings = None
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.parametrize("duplicate,status", [(False, 201), (True, 200)])
async def test_upload_status_location_and_chunk_size(client, monkeypatch, duplicate, status):
    async def ingest(pool, embeddings, owner, name, mime, data, chunk_size):
        assert owner == UUID(int=1) and chunk_size == 800 and data == b"policy"
        return UploadResult(
            document_id=UUID(int=10),
            filename=name,
            content_type=mime,
            size_bytes=len(data),
            page_count=None,
            chunk_count=1,
            chunk_size=chunk_size,
            chunk_overlap=50,
            embedding_model="gemini-embedding-2",
            created_at=datetime.now(UTC),
            duplicate=duplicate,
        )

    monkeypatch.setattr("documind.api.documents.ingest_document", ingest)
    response = await client.post(
        "/api/v1/documents?chunk_size=800", files={"file": ("policy.txt", b"policy", "text/plain")}
    )
    assert response.status_code == status
    assert response.headers["Location"] == f"/api/v1/documents/{UUID(int=10)}"
    assert response.json()["duplicate"] is duplicate


async def test_invalid_request_is_safe_json(client):
    response = await client.post(
        "/api/v1/documents?chunk_size=450", files={"file": ("file.txt", b"text")}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_invalid_pdf_is_rejected_before_storage(client):
    response = await client.post(
        "/api/v1/documents", files={"file": ("file.pdf", b"MZbinary", "application/pdf")}
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_pdf"


async def test_other_user_document_is_not_disclosed(client, monkeypatch):
    async def find(pool, owner, document_id):
        assert owner == UUID(int=1)

    monkeypatch.setattr("documind.api.documents.documents.get_document", find)
    response = await client.get(f"/api/v1/documents/{UUID(int=2)}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"


async def test_missing_auth_is_401(client):
    del app.dependency_overrides[get_user]
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"


async def test_provider_failure_is_safe_json(client, monkeypatch):
    async def ingest(*args):
        raise AppError(503, "embedding_unavailable", "Retry later.")

    monkeypatch.setattr("documind.api.documents.ingest_document", ingest)
    response = await client.post("/api/v1/documents", files={"file": ("policy.txt", b"text")})
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "embedding_unavailable", "message": "Retry later."}
    }


@pytest.mark.parametrize("exists,status", [(True, 204), (False, 404)])
async def test_delete_document_is_owner_scoped(client, monkeypatch, exists, status):
    async def remove(pool, owner, document_id):
        assert owner == UUID(int=1) and document_id == UUID(int=10)
        return exists

    monkeypatch.setattr("documind.api.documents.documents.delete_document", remove)
    response = await client.delete(f"/api/v1/documents/{UUID(int=10)}")
    assert response.status_code == status
    if exists:
        assert response.content == b""
    else:
        assert response.json()["error"]["code"] == "document_not_found"


async def test_delete_requires_authentication(client):
    del app.dependency_overrides[get_user]
    response = await client.delete(f"/api/v1/documents/{UUID(int=10)}")
    assert response.status_code == 401


async def test_delete_invalid_document_id_is_422(client):
    response = await client.delete("/api/v1/documents/not-a-uuid")
    assert response.status_code == 422
