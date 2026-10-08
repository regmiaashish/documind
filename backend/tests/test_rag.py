"""Evidence gating and citations must fail closed without live Gemini requests."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import ValidationError

from documind.exceptions import AppError
from documind.integrations.reranker import rerank
from documind.schemas.chat import ChatRequest, RetrievedChunk
from documind.services.chat import guarded_events
from documind.services.rag import REFUSAL, validate_answer
from documind.services.retrieval import fuse_rankings, retrieve


def chunk(number=1, similarity=0.9, keyword_match=False):
    return RetrievedChunk(
        chunk_id=UUID(int=number),
        document_id=UUID(int=10),
        filename="handbook.pdf",
        chunk_index=number - 1,
        page=1,
        content="Employees receive 20 days annual leave.",
        similarity=similarity,
        keyword_match=keyword_match,
    )


@pytest.mark.parametrize("question", ["", "   "])
def test_blank_question_rejected(question):
    with pytest.raises(ValidationError):
        ChatRequest(question=question)


@pytest.mark.parametrize(
    "filters",
    [
        {"created_after": "2026-01-01"},
        {"created_after": "2026-02-01T00:00:00Z", "created_before": "2026-01-01T00:00:00Z"},
        {"chunk_size": 450},
        {"retrieval_mode": "anything"},
    ],
)
def test_invalid_filters_rejected(filters):
    with pytest.raises(ValidationError):
        ChatRequest(question="Leave?", **filters)


def test_fusion_promotes_shared_evidence_and_deduplicates():
    first, second, shared = chunk(1), chunk(2), chunk(3)
    result = fuse_rankings([first, shared], [second, shared])
    assert result[0] == shared and len(result) == 3


@pytest.mark.parametrize(
    "text", ["20 days [2].", "20 days [0].", "20 days [1].\n\nAn uncited fact."]
)
def test_invalid_citations_refuse(text):
    assert validate_answer(text, [chunk()]) == (REFUSAL, [], True)


def test_single_source_draft_does_not_invent_a_citation():
    assert validate_answer("Mara Vale is SkyGuard.", [chunk()]) == (REFUSAL, [], True)


def test_unknown_citation_is_removed_when_a_valid_source_exists():
    answer, citations, refused = validate_answer("SkyGuard is Mara Vale [1, 2].", [chunk()])
    assert not refused and answer == "SkyGuard is Mara Vale [1]."
    assert [citation.source_id for citation in citations] == [1]


def test_grouped_valid_citations_are_accepted():
    answer, citations, refused = validate_answer(
        "SkyGuard protects Harbor City [1, 2].", [chunk(1), chunk(2)]
    )
    assert not refused and answer == "SkyGuard protects Harbor City [1, 2]."
    assert [citation.source_id for citation in citations] == [1, 2]


def test_uncited_multi_source_draft_still_refuses():
    assert validate_answer("Mara Vale is SkyGuard.", [chunk(1), chunk(2)]) == (REFUSAL, [], True)


def test_valid_citations_are_backed_by_actual_metadata():
    answer, citations, refused = validate_answer("20 days [1].", [chunk()])
    assert not refused and answer == "20 days [1]."
    assert citations[0].document_id == UUID(int=10)
    assert citations[0].page == 1 and citations[0].snippet == chunk().content


async def test_weak_context_skips_reranker(monkeypatch):
    search = AsyncMock(return_value=[chunk(similarity=0.1)])
    rank = AsyncMock()
    monkeypatch.setattr("documind.services.retrieval.search_chunks", search)
    monkeypatch.setattr("documind.services.retrieval.rerank", rank)
    embeddings = AsyncMock()
    assert (
        await retrieve(
            None, embeddings, None, UUID(int=1), ChatRequest(question="Mars?"), "hybrid_rerank"
        )
        == []
    )
    assert search.await_count == 2
    rank.assert_not_awaited()


async def test_exact_keyword_match_reaches_reranker_below_vector_threshold(monkeypatch):
    search = AsyncMock(
        side_effect=[[chunk(similarity=0.1)], [chunk(similarity=0.1, keyword_match=True)]]
    )
    rank = AsyncMock(return_value=[chunk(similarity=0.1, keyword_match=True)])
    monkeypatch.setattr("documind.services.retrieval.search_chunks", search)
    monkeypatch.setattr("documind.services.retrieval.rerank", rank)
    result = await retrieve(
        None,
        AsyncMock(),
        AsyncMock(),
        UUID(int=1),
        ChatRequest(question="SkyGuard"),
        "hybrid_rerank",
    )
    assert result[0].keyword_match
    rank.assert_awaited_once()


async def test_exact_keyword_match_survives_empty_reranker_result(monkeypatch):
    hit = chunk(similarity=0.1, keyword_match=True)
    search = AsyncMock(side_effect=[[chunk(similarity=0.1)], [hit]])
    monkeypatch.setattr("documind.services.retrieval.search_chunks", search)
    monkeypatch.setattr("documind.services.retrieval.rerank", AsyncMock(return_value=[]))
    result = await retrieve(
        None,
        AsyncMock(),
        AsyncMock(),
        UUID(int=1),
        ChatRequest(question="SkyGuard"),
        "hybrid_rerank",
    )
    assert result == [hit]


@pytest.mark.parametrize("mode,calls", [("vector", 1), ("hybrid", 2)])
async def test_modes_share_owner_and_filters(monkeypatch, mode, calls):
    search = AsyncMock(return_value=[chunk()])
    monkeypatch.setattr("documind.services.retrieval.search_chunks", search)
    request = ChatRequest(question="Leave?", document_ids=[UUID(int=10)])
    assert await retrieve(None, AsyncMock(), None, UUID(int=1), request, mode) == [chunk()]
    assert search.await_count == calls
    for call in search.await_args_list:
        assert call.args[1:3] == (UUID(int=1), request)


@pytest.mark.parametrize(
    "ranking",
    [
        '{"sources":[]}',
        '{"sources":[{"source_id":2,"relevance":1}]}',
        '{"sources":[{"source_id":1,"relevance":1},{"source_id":1,"relevance":1}]}',
        '{"sources":[{"source_id":1,"relevance":2}]}',
        "not json",
    ],
)
async def test_invalid_reranker_output_fails_closed(ranking):
    llm = AsyncMock()
    llm.generate.return_value = ranking
    with pytest.raises(AppError, match="Could not rank"):
        await rerank(llm, "Leave?", [chunk()])


async def test_reranker_order_and_relevance_gate():
    llm = AsyncMock()
    llm.generate.return_value = (
        '{"sources":[{"source_id":1,"relevance":0.1},{"source_id":2,"relevance":0.9}]}'
    )
    assert await rerank(llm, "Leave?", [chunk(1), chunk(2)]) == [chunk(2)]


async def test_no_evidence_refuses_without_generation(monkeypatch):
    monkeypatch.setattr("documind.services.rag.retrieve", AsyncMock(return_value=[]))
    llm = AsyncMock()
    events = [
        event
        async for event in guarded_events(
            None, None, llm, UUID(int=1), ChatRequest(question="Mars?")
        )
    ]
    result = next(data for event, data in events if event == "answer")
    assert result["refused"] and result["answer"] == REFUSAL and result["citations"] == []
    assert events[-1] == ("done", {})
    llm.stream.assert_not_called()


async def test_stream_validates_draft_before_final_answer(monkeypatch):
    monkeypatch.setattr("documind.services.rag.retrieve", AsyncMock(return_value=[chunk()]))

    class LLM:
        async def stream(self, system, prompt):
            assert "untrusted data" in system and '"source_id": 1' in prompt
            yield "Unsupported [9].", "fake-model"

        async def generate(self, system, prompt):
            return '{"answer":"I don\'t know based on the uploaded documents."}'

    events = [
        event
        async for event in guarded_events(
            None, None, LLM(), UUID(int=1), ChatRequest(question="Leave?")
        )
    ]
    assert ("token", {"text": "Unsupported [9]."}) in events
    result = next(data for event, data in events if event == "answer")
    assert result["refused"] and result["answer"] == REFUSAL


async def test_provider_error_becomes_safe_stream_event(monkeypatch):
    monkeypatch.setattr(
        "documind.services.rag.retrieve",
        AsyncMock(side_effect=AppError(503, "provider_failure", "Please retry.")),
    )
    events = [
        event
        async for event in guarded_events(
            None, None, None, UUID(int=1), ChatRequest(question="Leave?")
        )
    ]
    assert events[-2:] == [
        ("error", {"code": "provider_failure", "message": "Please retry.", "status": 503}),
        ("done", {}),
    ]
