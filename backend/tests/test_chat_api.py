"""Swagger JSON, browser SSE, authentication, and source routes share one contract."""

from datetime import UTC
from uuid import UUID

import httpx
import pytest
from fastapi import Request

from documind.core.dependencies import get_embeddings, get_llm, get_pool, get_user
from documind.main import app


@pytest.fixture
async def client():
    async def pool():
        return None

    async def user(request: Request):
        request.state.user_id = UUID(int=2 if request.headers.get("x-test-user") == "bob" else 1)
        return request.state.user_id

    app.dependency_overrides[get_pool] = pool
    app.dependency_overrides[get_user] = user
    app.state.embeddings = None
    app.state.llm = None
    app.state.limiter.reset()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http
    app.dependency_overrides.clear()


@pytest.mark.parametrize("stream", [False, True])
async def test_json_and_sse_final_contract(client, monkeypatch, stream):
    async def events(pool, embeddings, llm, owner, request):
        assert owner == UUID(int=1) and request.question == "Leave?"
        yield (
            "answer",
            {
                "answer": "20 days [1].",
                "citations": [],
                "refused": False,
                "retrieval_mode": "vector",
                "model": "fake",
                "latency_ms": 12,
            },
        )
        yield "done", {}

    monkeypatch.setattr("documind.api.chat.guarded_events", events)
    response = await client.post(
        "/api/v1/chat-messages", json={"question": "Leave?", "stream": stream}
    )
    assert response.status_code == 200
    if stream:
        assert response.headers["content-type"].startswith("text/event-stream")
        assert "event: answer" in response.text and "event: done" in response.text
    else:
        assert response.json()["answer"] == "20 days [1]."


async def test_chat_requires_authentication(client):
    del app.dependency_overrides[get_user]
    response = await client.post("/api/v1/chat-messages", json={"question": "Leave?"})
    assert response.status_code == 401


async def test_authentication_dependency_resolves_bearer_user(client, monkeypatch):
    import hashlib

    del app.dependency_overrides[get_user]

    async def find_user(pool, digest):
        assert digest == hashlib.sha256(b"test-bearer").hexdigest()
        return UUID(int=1)

    async def events(pool, embeddings, llm, owner, request):
        assert owner == UUID(int=1)
        yield (
            "answer",
            {
                "answer": "20 days [1].",
                "citations": [],
                "refused": False,
                "retrieval_mode": "vector",
                "latency_ms": 1,
            },
        )

    monkeypatch.setattr("documind.core.dependencies.find_user", find_user)
    monkeypatch.setattr("documind.api.chat.guarded_events", events)
    response = await client.post(
        "/api/v1/chat-messages",
        headers={"Authorization": "Bearer test-bearer"},
        json={"question": "Leave?"},
    )
    assert response.status_code == 200


async def test_ai_clients_are_injected_and_overridable(client, monkeypatch):
    embeddings_client = object()
    llm_client = object()
    async def embeddings_dependency():
        return embeddings_client

    async def llm_dependency():
        return llm_client

    app.dependency_overrides[get_embeddings] = embeddings_dependency
    app.dependency_overrides[get_llm] = llm_dependency

    async def events(pool, embeddings, llm, owner, request):
        assert embeddings is embeddings_client and llm is llm_client
        yield (
            "answer",
            {
                "answer": "20 days [1].",
                "citations": [],
                "refused": False,
                "retrieval_mode": "vector",
                "latency_ms": 1,
            },
        )

    monkeypatch.setattr("documind.api.chat.guarded_events", events)
    response = await client.post("/api/v1/chat-messages", json={"question": "Leave?"})
    assert response.status_code == 200


async def test_invalid_question_is_422(client):
    response = await client.post("/api/v1/chat-messages", json={"question": " "})
    assert response.status_code == 422


async def test_provider_error_json_is_safe(client, monkeypatch):
    async def events(*args):
        yield "error", {"code": "generation_unavailable", "message": "Please retry."}
        yield "done", {}

    monkeypatch.setattr("documind.api.chat.guarded_events", events)
    response = await client.post("/api/v1/chat-messages", json={"question": "Leave?"})
    assert response.status_code == 503 and response.json()["error"]["message"] == "Please retry."


async def test_other_user_source_returns_404(client, monkeypatch):
    async def source(pool, owner, document_id, chunk_index):
        assert owner == UUID(int=1) and chunk_index == 0

    monkeypatch.setattr("documind.api.documents.get_chunk", source)
    response = await client.get(f"/api/v1/documents/{UUID(int=2)}/chunks/0")
    assert response.status_code == 404


async def test_confirmation_route_uses_authenticated_owner(client, monkeypatch):
    from datetime import datetime

    from documind.schemas.tools import Ticket

    async def confirm(pool, owner, action_id):
        assert owner == UUID(int=1) and action_id == UUID(int=3)
        return Ticket(
            id=UUID(int=4), subject="Damage", body="Damaged package", created_at=datetime.now(UTC)
        )

    monkeypatch.setattr("documind.api.actions.confirm_ticket", confirm)
    response = await client.post(f"/api/v1/actions/{UUID(int=3)}/confirmation")
    assert response.status_code == 200 and response.json()["id"] == str(UUID(int=4))


async def test_chat_limit_shared_by_json_and_sse_and_isolated_by_user(client, monkeypatch):
    calls = 0

    async def events(*args):
        nonlocal calls
        calls += 1
        yield (
            "answer",
            {
                "answer": "20 days [1].",
                "citations": [],
                "refused": False,
                "retrieval_mode": "vector",
                "latency_ms": 1,
            },
        )
        yield "done", {}

    monkeypatch.setattr("documind.api.chat.guarded_events", events)
    for index in range(5):
        response = await client.post(
            "/api/v1/chat-messages", json={"question": "Leave?", "stream": bool(index % 2)}
        )
        assert response.status_code == 200
    response = await client.post(
        "/api/v1/chat-messages", json={"question": "Leave?", "stream": True}
    )
    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json()["error"]["code"] == "rate_limit_exceeded"
    assert calls == 5
    response = await client.post(
        "/api/v1/chat-messages", headers={"x-test-user": "bob"}, json={"question": "Leave?"}
    )
    assert response.status_code == 200 and calls == 6
