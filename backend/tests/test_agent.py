"""Tool boundaries, bounded failure, and confirmation behavior without provider calls."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from documind.core.budget import GenerationBudget
from documind.core.config import settings
from documind.exceptions import AppError
from documind.schemas.chat import ChatRequest
from documind.schemas.tools import PendingAction, tool_arguments
from documind.services.agent import agent_events, read_order
from documind.services.router import needs_tools


class Planner:
    def __init__(self, *steps):
        self.steps = iter(steps)

    async def generate(self, system, prompt, budget):
        budget.reserve(system, prompt, 100)
        return json.dumps(next(self.steps))


async def run(planner, question):
    return [
        item
        async for item in agent_events(
            None, None, planner, UUID(int=1), ChatRequest(question=question)
        )
    ]


@pytest.mark.parametrize(
    "question,expected",
    [
        ("What is the refund policy?", False),
        ("Who is SkyGuard?", False),
        ("Where is ORD-1001?", True),
        ("Create a support ticket about my damaged package", True),
        ("What does the document say about creating tickets?", False),
    ],
)
def test_router(question, expected):
    assert needs_tools(question) is expected


def test_owner_and_confirmation_cannot_be_model_arguments():
    with pytest.raises(ValidationError):
        tool_arguments.validate_python(
            {
                "tool": "create_ticket",
                "subject": "Damage",
                "body": "Damaged package",
                "owner_id": str(UUID(int=2)),
                "confirmed": True,
            }
        )


def test_budget_prevents_next_provider_attempt(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_tokens", 1000)
    budget = GenerationBudget()
    budget.reserve("rules", "question", 100)
    with pytest.raises(AppError, match="tool budget"):
        budget.reserve("rules", "question", 1000)
    assert budget.reserved_tokens < 1000


def test_cost_budget_independent_of_token_limit(monkeypatch):
    monkeypatch.setattr(settings, "agent_max_cost_usd", 0.00001)
    with pytest.raises(AppError):
        GenerationBudget().reserve("rules", "question", 100)


async def test_order_answer_uses_database_facts(monkeypatch):
    async def order(pool, owner, order_id):
        assert owner == UUID(int=1) and order_id == "ORD-1001"
        return {"id": order_id, "status": "shipped", "delivery_date": "2026-10-12"}

    monkeypatch.setattr("documind.services.agent.get_order_status", order)
    events = await run(
        Planner({"tool": "get_order_status", "order_id": "ORD-1001"}, {"tool": "finish"}),
        "Where is ORD-1001?",
    )
    result = events[-1][1]
    assert "shipped" in result["answer"] and result["route"] == "agent"
    assert result["citations"] == [] and result["confirmation"] is None


async def test_independent_order_reads_run_concurrently(monkeypatch):
    active = 0
    peak = 0

    async def order(pool, owner, order_id):
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        await asyncio.sleep(0)
        active -= 1
        return {"id": order_id, "status": "shipped", "delivery_date": "2026-10-12"}

    monkeypatch.setattr("documind.services.agent.get_order_status", order)
    plan = {
        "calls": [
            {"tool": "get_order_status", "order_id": "ORD-1001"},
            {"tool": "get_order_status", "order_id": "ORD-1002"},
        ]
    }
    events = await run(Planner(plan, {"tool": "finish"}), "Status of ORD-1001 and ORD-1002?")
    assert peak == 2 and "ORD-1002" in events[-1][1]["answer"]


async def test_unavailable_order_is_honest_and_retries_once(monkeypatch):
    calls = 0

    async def order(*args):
        nonlocal calls
        calls += 1
        raise TimeoutError

    monkeypatch.setattr("documind.services.agent.get_order_status", order)
    with pytest.raises(AppError) as failure:
        await read_order(None, UUID(int=1), "ORD-1001")
    assert calls == 2 and failure.value.code == "tool_unavailable"


async def test_unknown_or_foreign_order_is_not_disclosed(monkeypatch):
    async def order(*args):
        return None

    monkeypatch.setattr("documind.services.agent.get_order_status", order)
    events = await run(
        Planner({"tool": "get_order_status", "order_id": "ORD-2001"}), "Where is ORD-2001?"
    )
    assert events[-1][1]["refused"] and "not found" in events[-1][1]["answer"]


async def test_ticket_is_only_a_pending_draft(monkeypatch):
    async def draft(pool, owner, arguments):
        assert owner == UUID(int=1) and arguments.subject == "Damage"
        return PendingAction(
            id=UUID(int=3),
            subject=arguments.subject,
            body=arguments.body,
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        )

    monkeypatch.setattr("documind.services.agent.draft_ticket", draft)
    events = await run(
        Planner({"tool": "create_ticket", "subject": "Damage", "body": "Package arrived damaged."}),
        "Create a support ticket for my damaged package",
    )
    result = events[-1][1]
    assert result["confirmation"]["id"] == str(UUID(int=3))
    assert "only when" in result["answer"]


async def test_model_cannot_draft_ticket_for_order_only_request():
    with pytest.raises(AppError) as failure:
        await run(
            Planner(
                {"tool": "create_ticket", "subject": "Damage", "body": "Package arrived damaged."}
            ),
            "Where is ORD-1001?",
        )
    assert failure.value.code == "ticket_not_requested"


async def test_bad_model_arguments_are_rejected():
    with pytest.raises(AppError) as failure:
        await run(Planner({"tool": "delete_everything"}), "Where is ORD-1001?")
    assert failure.value.code == "invalid_tool_arguments"


async def test_model_cannot_invent_order_id():
    with pytest.raises(AppError) as failure:
        await run(
            Planner({"tool": "get_order_status", "order_id": "ORD-9999"}), "Where is ORD-1001?"
        )
    assert failure.value.code == "order_id_not_requested"


async def test_repeated_tool_request_stops_without_unbounded_loop(monkeypatch):
    calls = 0

    async def order(pool, owner, order_id):
        nonlocal calls
        calls += 1
        return {"id": order_id, "status": "shipped", "delivery_date": "2026-10-12"}

    monkeypatch.setattr("documind.services.agent.get_order_status", order)
    step = {"tool": "get_order_status", "order_id": "ORD-1001"}
    events = await run(Planner(step, step), "Where is ORD-1001?")
    assert calls == 1 and "shipped" in events[-1][1]["answer"]


async def test_search_tool_preserves_filters_and_grounding(monkeypatch):
    async def answer(pool, embeddings, llm, owner, request, budget):
        assert request.document_ids == [UUID(int=10)] and request.retrieval_mode == "hybrid"
        assert owner == UUID(int=1) and isinstance(budget, GenerationBudget)
        yield "answer", {"answer": "20 days [1].", "route": "rag", "latency_ms": 1}

    monkeypatch.setattr("documind.services.rag.answer_events", answer)
    request = ChatRequest(
        question="Check the policy for ORD-1001 status", document_ids=[UUID(int=10)]
    )
    events = [
        event
        async for event in agent_events(
            None,
            None,
            Planner({"tool": "search_docs", "question": "Annual leave?"}),
            UUID(int=1),
            request,
        )
    ]
    assert events[-1][1]["route"] == "agent"
