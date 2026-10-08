"""Exercise the real HTTP boundary offline with deterministic Gemini responses."""

import json
import math

import httpx
import pytest

from documind.exceptions import AppError
from documind.integrations.embeddings import GeminiEmbeddings


async def test_embedding_batches_preserve_order_and_dimensions():
    requests = []

    def respond(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert request.headers["x-goog-api-key"] == "test-key"
        assert "test-key" not in str(request.url)
        vectors = []
        for entry in payload["requests"]:
            assert entry["outputDimensionality"] == 768
            text = entry["content"]["parts"][0]["text"]
            index = int(text.rsplit(" ", 1)[1])
            values = [0.0] * 768
            values[index] = 2.0
            vectors.append({"values": values})
        return httpx.Response(200, json={"embeddings": vectors})

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        vectors = await GeminiEmbeddings(client, "test-key").embed_documents(
            [f"chunk {i}" for i in range(33)], "policy.pdf"
        )
    assert [len(p["requests"]) for p in requests] == [32, 1]
    assert all(vector[i] == 1.0 for i, vector in enumerate(vectors))
    assert all(math.isclose(sum(x * x for x in vector), 1) for vector in vectors)


@pytest.mark.parametrize("values", [[1.0], [0.0] * 768, [float("inf")] * 768])
async def test_invalid_vectors_fail_safely(values):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"embeddings": [{"values": values}]})
    )
    # JSON cannot encode infinity; send its string representation to test validation.
    if not all(math.isfinite(x) for x in values):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"embeddings": [{"values": ["inf"] * 768}]})
        )
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(AppError) as caught:
            await GeminiEmbeddings(client, "key").embed_documents(["policy"], "file.txt")
    assert caught.value.code == "invalid_embeddings"


async def test_rate_limit_retries_are_bounded(monkeypatch):
    attempts = []
    delays = []

    def respond(request):
        attempts.append(request)
        return httpx.Response(429, json={"error": "private provider details"})

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr("documind.integrations.embeddings.asyncio.sleep", sleep)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(AppError) as caught:
            await GeminiEmbeddings(client, "secret").embed_documents(["policy"], "file.txt")
    assert len(attempts) == 3 and delays == [0.5, 1.0]
    assert caught.value.status == 503
    assert "secret" not in caught.value.message and "private" not in caught.value.message


async def test_missing_key_does_not_send_request():
    def respond(request):
        raise AssertionError("No request should be sent")

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(AppError) as caught:
            await GeminiEmbeddings(client, "").embed_documents(["policy"], "file.txt")
    assert caught.value.code == "missing_api_key"


async def test_query_uses_documented_question_answering_prefix():
    def respond(request):
        payload = json.loads(request.content)
        text = payload["requests"][0]["content"]["parts"][0]["text"]
        assert text == "task: question answering | query: Leave?"
        assert "taskType" not in payload["requests"][0]
        return httpx.Response(200, json={"embeddings": [{"values": [1.0] + [0.0] * 767}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await GeminiEmbeddings(client, "fake-key").embed_query("Leave?")
    assert len(result) == 768 and result[0] == 1
