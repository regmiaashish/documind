"""Provider fallback and interrupted native streams are bounded and explicit."""

import json

import httpx
import pytest

from documind.core.budget import GenerationBudget
from documind.core.config import settings
from documind.exceptions import AppError
from documind.integrations.llm import GeminiLLM


async def test_agent_budget_reserves_failed_primary_before_fallback(monkeypatch):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429)

    budget = GenerationBudget()
    monkeypatch.setattr(settings, "agent_max_tokens", 1400)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AppError) as failure:
            await GeminiLLM(client, "fake-key").generate("Rules", "Question", budget=budget)
    assert failure.value.code == "agent_budget_exceeded"
    assert calls == 1 and budget.reserved_tokens > 1000


def event(text, finish=None):
    candidate = {"content": {"parts": [{"text": text}]}}
    if finish:
        candidate["finishReason"] = finish
    return "data: " + json.dumps({"candidates": [candidate]}) + "\n\n"


async def test_generation_falls_back_once():
    calls = []

    def handler(request):
        calls.append(request)
        config = json.loads(request.content)["generationConfig"]
        assert config["thinkingConfig"]["thinkingLevel"] == (
            "minimal" if len(calls) == 1 else "low"
        )
        if len(calls) == 1:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"sources":[]}'}]}, "finishReason": "STOP"}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GeminiLLM(client, "fake-key").generate("Rank", "Question")
    assert result == '{"sources":[]}' and len(calls) == 2
    assert settings.llm_primary_model in str(calls[0].url)
    assert settings.llm_fallback_model in str(calls[1].url)


async def test_stream_fallback_before_first_token():
    calls = []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(503)
            if len(calls) == 1
            else httpx.Response(200, text=event("20 days ") + event("[1].", "STOP"))
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = [part async for part in GeminiLLM(client, "fake-key").stream("System", "Question")]
    assert [text for text, _ in result] == ["20 days ", "[1]."]
    assert len(calls) == 2


@pytest.mark.parametrize("tail", ["", "data: bad-json\n\n", event("", "MAX_TOKENS")])
async def test_interruption_never_appends_fallback_answer(tail):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, text=event("Draft ") + tail)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AppError) as caught:
            _ = [part async for part in GeminiLLM(client, "fake-key").stream("System", "Question")]
    assert caught.value.code == "stream_interrupted" and len(calls) == 1


async def test_missing_key_does_not_call_provider():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: pytest.fail("Unexpected request"))
    ) as client:
        with pytest.raises(AppError) as caught:
            await GeminiLLM(client, "").generate("System", "Question")
    assert caught.value.code == "missing_api_key"
