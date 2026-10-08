"""Evaluation measures real pipeline output and leaves semantic support to review."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from pydantic import SecretStr

from documind.core.config import settings
from documind.evaluation.report import render_report
from documind.evaluation.runner import (
    configuration,
    evaluate_case,
    load_questions,
    retrieval_hit,
    run_evaluation,
    save_run,
    validate_evidence,
)
from documind.evaluation.schemas import MODES, SIZES, EvaluationRun, Question, Result
from documind.exceptions import AppError
from documind.schemas.chat import ChatAnswer, RetrievedChunk

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "data/evaluation/questions.json"
DOCUMENT = ROOT / "data/sample/handbook.pdf"


def question() -> Question:
    return load_questions(DATASET)[0]


def chunk(number=1, page=1, text="20 days of paid annual leave") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=UUID(int=number),
        document_id=UUID(int=10),
        filename="handbook.pdf",
        chunk_index=number - 1,
        page=page,
        content=text,
        similarity=0.9,
    )


def result(case=None, size=300, mode="vector", error=None) -> Result:
    answer = ChatAnswer(
        answer="20 days [1].", citations=[], refused=False, retrieval_mode=mode, latency_ms=10
    )
    return Result(
        case=case or question(),
        chunk_size=size,
        retrieval_mode=mode,
        chunks=[chunk()],
        answer=None if error else answer,
        latency_ms=10,
        hit_at_5=True,
        error=error,
    )


def evaluation(rows=None) -> EvaluationRun:
    return EvaluationRun(
        started_at=datetime.now(UTC),
        document_sha256="document",
        questions_sha256="questions",
        configuration={},
        results=rows or [],
    )


def test_dataset_matches_actual_sample_pdf():
    questions = load_questions(DATASET)
    assert len(questions) == 15 and sum(case.expected_refusal for case in questions) == 3
    validate_evidence(DOCUMENT.read_bytes(), questions)


def test_wrong_gold_evidence_is_rejected_before_provider_calls():
    case = question().model_copy(update={"evidence": ["a fact absent from this PDF"]})
    with pytest.raises(ValueError, match="expected evidence"):
        validate_evidence(DOCUMENT.read_bytes(), [case])


def test_hit_requires_expected_page_and_all_evidence_within_top_five():
    case = question()
    assert retrieval_hit(case, [chunk(text="20 DAYS\nof paid annual leave")]) is True
    assert retrieval_hit(case, [chunk(page=2)]) is False
    assert (
        retrieval_hit(case, [chunk(index, text="irrelevant") for index in range(1, 6)] + [chunk(6)])
        is False
    )
    assert (
        retrieval_hit(case.model_copy(update={"evidence": ["20 days", "March 31"]}), [chunk()])
        is False
    )
    assert retrieval_hit(case.model_copy(update={"expected_refusal": True}), []) is None


def test_manifest_excludes_credentials(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("never-save-this"))
    snapshot = configuration(UUID(int=1))
    assert "never-save-this" not in str(snapshot)
    assert "database_url" not in snapshot and "gemini_api_key" not in snapshot
    assert len(snapshot["pipeline_sha256"]) == 64


async def test_case_records_same_retrieval_used_for_answer(monkeypatch):
    async def events(pool, embeddings, llm, owner, request, on_retrieval):
        assert owner == UUID(int=1) and request.document_ids == [UUID(int=10)]
        on_retrieval([chunk()])
        yield "answer", result().answer.model_dump(mode="json")

    monkeypatch.setattr("documind.evaluation.runner.answer_events", events)
    measured = await evaluate_case(
        None, None, None, UUID(int=1), UUID(int=10), 300, "vector", question()
    )
    assert measured.hit_at_5 and measured.chunks[0].chunk_id == UUID(int=1)
    assert measured.supported is None and measured.correct is None


async def test_provider_failure_is_saved_as_error_not_refusal(monkeypatch):
    async def events(*args, **kwargs):
        raise AppError(503, "generation_unavailable", "Please retry.")
        yield

    monkeypatch.setattr("documind.evaluation.runner.answer_events", events)
    measured = await evaluate_case(
        None, None, None, UUID(int=1), UUID(int=10), 300, "vector", question()
    )
    assert measured.error == "generation_unavailable" and measured.answer is None
    assert measured.supported is None


def test_report_does_not_infer_support_or_choose_winner_before_review():
    report = render_report(evaluation([result()]))
    assert "1 pending" in report and "No winner selected" in report


def test_report_rejects_duplicate_results():
    with pytest.raises(ValueError, match="Duplicate"):
        render_report(evaluation([result(), result()]))


def test_failed_request_cannot_be_marked_supported():
    row = result(error="generation_unavailable")
    row.supported = True
    with pytest.raises(ValueError, match="failed request"):
        render_report(evaluation([row]))


def test_completed_review_selects_measured_configuration():
    rows = []
    for size in SIZES:
        for mode in MODES:
            for case in load_questions(DATASET):
                row = result(case, size, mode)
                row.correct = size == 800 and mode == "hybrid"
                row.supported = row.correct if not case.expected_refusal else None
                rows.append(row)
    assert "**800 / hybrid**" in render_report(evaluation(rows))


async def test_resume_preserves_review_and_skips_finished_case(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("fake-key"))

    @asynccontextmanager
    async def pool():
        yield None

    monkeypatch.setattr("documind.evaluation.runner.database_pool", pool)
    monkeypatch.setattr(
        "documind.evaluation.runner.ingest_document",
        AsyncMock(return_value=SimpleNamespace(document_id=UUID(int=10))),
    )
    calls = []

    async def measure(pool, embeddings, llm, owner, document_id, size, mode, case):
        calls.append((case.id, size, mode))
        return result(case, size, mode)

    monkeypatch.setattr("documind.evaluation.runner.evaluate_case", measure)
    output = tmp_path / "results.json"
    await run_evaluation(DOCUMENT, DATASET, output, UUID(int=1), 0, False)
    assert len(calls) == 90
    saved = EvaluationRun.model_validate_json(output.read_text())
    saved.results[0].supported = True
    saved.results[0].review_notes = "Manually checked"
    saved.results.pop()
    save_run(output, saved)
    calls.clear()
    await run_evaluation(DOCUMENT, DATASET, output, UUID(int=1), 0, False)
    assert len(calls) == 1
    resumed = EvaluationRun.model_validate_json(output.read_text())
    assert resumed.results[0].supported and resumed.results[0].review_notes == "Manually checked"


async def test_changed_settings_cannot_mix_with_existing_results(tmp_path, monkeypatch):
    output = tmp_path / "results.json"
    import hashlib

    saved = EvaluationRun(
        started_at=datetime.now(UTC),
        document_sha256=hashlib.sha256(DOCUMENT.read_bytes()).hexdigest(),
        questions_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        configuration=configuration(UUID(int=1)),
    )
    save_run(output, saved)
    monkeypatch.setattr(settings, "similarity_threshold", 0.99)
    with pytest.raises(ValueError, match="different inputs/settings"):
        await run_evaluation(DOCUMENT, DATASET, output, UUID(int=1), 0, False)


def test_all_failed_cases_do_not_produce_a_winner():
    rows = [
        result(case, size, mode, error="generation_unavailable")
        for size in SIZES
        for mode in MODES
        for case in load_questions(DATASET)
    ]
    assert "No winner selected" in render_report(evaluation(rows))


async def test_retry_failed_only_repeats_failed_cases(tmp_path, monkeypatch):
    import hashlib

    output = tmp_path / "results.json"
    rows = [
        result(case, size, mode)
        for size in SIZES
        for mode in MODES
        for case in load_questions(DATASET)
    ]
    rows[0] = result(error="generation_unavailable")
    rows[1].supported = True
    saved = EvaluationRun(
        started_at=datetime.now(UTC),
        document_sha256=hashlib.sha256(DOCUMENT.read_bytes()).hexdigest(),
        questions_sha256=hashlib.sha256(DATASET.read_bytes()).hexdigest(),
        configuration=configuration(UUID(int=1)),
        results=rows,
    )
    save_run(output, saved)
    monkeypatch.setattr(settings, "gemini_api_key", SecretStr("fake-key"))

    @asynccontextmanager
    async def pool():
        yield None

    monkeypatch.setattr("documind.evaluation.runner.database_pool", pool)
    monkeypatch.setattr(
        "documind.evaluation.runner.ingest_document",
        AsyncMock(return_value=SimpleNamespace(document_id=UUID(int=10))),
    )
    measure = AsyncMock(return_value=result())
    monkeypatch.setattr("documind.evaluation.runner.evaluate_case", measure)
    await run_evaluation(DOCUMENT, DATASET, output, UUID(int=1), 0, True)
    assert measure.await_count == 1
    resumed = EvaluationRun.model_validate_json(output.read_text())
    assert len(resumed.results) == 90 and resumed.results[0].supported is True
