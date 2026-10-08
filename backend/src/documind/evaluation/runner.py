"""Run each case once through real retrieval and generation, saving progress after each."""

import asyncio
import hashlib
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

import asyncpg
import httpx
from pydantic import TypeAdapter

from documind.core.config import settings
from documind.core.db import database_pool
from documind.evaluation.schemas import MODES, SIZES, EvaluationRun, Question, Result
from documind.exceptions import AppError
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM
from documind.schemas.chat import ChatAnswer, ChatRequest, RetrievalMode, RetrievedChunk
from documind.services.ingestion import ingest_document
from documind.services.parsing import parse_file
from documind.services.rag import answer_events


def configuration(owner: UUID) -> dict:
    names = (
        "embedding_model",
        "embedding_dimensions",
        "chunk_overlap",
        "max_chunks",
        "llm_primary_model",
        "llm_fallback_model",
        "llm_max_output_tokens",
        "retrieval_candidates",
        "context_top_n",
        "similarity_threshold",
        "request_timeout_seconds",
    )
    package = Path(__file__).resolve().parents[1]
    source = b"".join(
        path.read_bytes()
        for path in sorted(package.rglob("*.py"))
        if "evaluation" not in path.relative_to(package).parts
    )
    return {
        **{name: getattr(settings, name) for name in names},
        "owner_id": str(owner),
        "pipeline_sha256": hashlib.sha256(source).hexdigest(),
    }


def load_questions(path: Path) -> list[Question]:
    questions = TypeAdapter(list[Question]).validate_json(path.read_text())
    if len(questions) != 15 or len({case.id for case in questions}) != 15:
        raise ValueError("Evaluation needs exactly 15 uniquely identified questions.")
    if any(
        not case.evidence or case.page is None for case in questions if not case.expected_refusal
    ):
        raise ValueError("Answerable questions need expected page and evidence phrases.")
    return questions


def normalize(text: str) -> str:
    return re.sub(r"\W+", " ", text.lower()).strip()


def validate_evidence(data: bytes, questions: list[Question]) -> None:
    pages, _ = parse_file(data, "application/pdf")
    text = {page: normalize(content) for page, content in pages}
    for case in questions:
        if not case.expected_refusal and any(
            normalize(phrase) not in text.get(case.page, "") for phrase in case.evidence
        ):
            raise ValueError(
                f"{case.id}: expected evidence was not found on page {case.page} of this PDF."
            )


def retrieval_hit(case: Question, chunks: list[RetrievedChunk]) -> bool | None:
    if case.expected_refusal:
        return None
    passages = [normalize(chunk.content) for chunk in chunks[:5] if chunk.page == case.page]
    return all(any(normalize(phrase) in text for text in passages) for phrase in case.evidence)


def save_run(path: Path, run: EvaluationRun) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(run.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


async def evaluate_case(
    pool: asyncpg.Pool,
    embeddings: GeminiEmbeddings,
    llm: GeminiLLM,
    owner: UUID,
    document_id: UUID,
    size: Literal[300, 800],
    mode: RetrievalMode,
    case: Question,
) -> Result:
    started = time.monotonic()
    chunks: list[RetrievedChunk] = []
    answer = None
    error = None
    try:
        request = ChatRequest(
            question=case.question, document_ids=[document_id], chunk_size=size, retrieval_mode=mode
        )
        async with asyncio.timeout(settings.request_timeout_seconds):
            async for event, payload in answer_events(
                pool, embeddings, llm, owner, request, on_retrieval=chunks.extend
            ):
                if event == "answer":
                    answer = ChatAnswer.model_validate(payload)
        if answer is None:
            error = "empty_answer"
    except AppError as failure:
        error = failure.code
    except (TimeoutError, OSError, asyncpg.PostgresError) as failure:
        error = type(failure).__name__
    return Result(
        case=case,
        chunk_size=size,
        retrieval_mode=mode,
        chunks=chunks,
        answer=answer,
        latency_ms=round((time.monotonic() - started) * 1000),
        hit_at_5=retrieval_hit(case, chunks),
        error=error,
    )


async def run_evaluation(
    document: Path,
    questions_path: Path,
    output: Path,
    owner: UUID,
    delay: float,
    retry_failed: bool,
) -> None:
    if output.resolve() in (document.resolve(), questions_path.resolve()):
        raise ValueError("The output must not overwrite the sample document or question dataset.")
    questions = load_questions(questions_path)
    data = document.read_bytes()
    validate_evidence(data, questions)
    snapshot = EvaluationRun(
        started_at=datetime.now(UTC),
        document_sha256=hashlib.sha256(data).hexdigest(),
        questions_sha256=hashlib.sha256(questions_path.read_bytes()).hexdigest(),
        configuration=configuration(owner),
    )
    if output.exists():
        saved = EvaluationRun.model_validate_json(output.read_text())
        if (saved.document_sha256, saved.questions_sha256, saved.configuration) != (
            snapshot.document_sha256,
            snapshot.questions_sha256,
            snapshot.configuration,
        ):
            raise ValueError(
                "Existing results use different inputs/settings. Choose a new --output file."
            )
        snapshot = saved
        if retry_failed:
            snapshot.results = [result for result in snapshot.results if result.error is None]
    complete = {
        (result.case.id, result.chunk_size, result.retrieval_mode) for result in snapshot.results
    }
    if len(complete) == len(questions) * len(SIZES) * len(MODES):
        print("All 90 cases already recorded. Run the report command.")
        return
    key = settings.gemini_api_key.get_secret_value().strip()
    if not key:
        raise ValueError("Add GEMINI_API_KEY to the root .env before running evaluation.")
    async with database_pool() as pool, httpx.AsyncClient() as client:
        embeddings, llm = GeminiEmbeddings(client, key), GeminiLLM(client, key)
        for size in SIZES:
            uploaded = await ingest_document(
                pool, embeddings, owner, document.name, "application/pdf", data, size
            )
            for mode in MODES:
                for case in questions:
                    if (case.id, size, mode) in complete:
                        continue
                    result = await evaluate_case(
                        pool, embeddings, llm, owner, uploaded.document_id, size, mode, case
                    )
                    snapshot.results.append(result)
                    save_run(output, snapshot)
                    print(
                        f"{size} {mode} {case.id}: {result.error or 'recorded'} ({result.latency_ms} ms)",
                        flush=True,
                    )
                    await asyncio.sleep(delay)
