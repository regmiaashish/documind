"""Summarize saved measurements without treating citation presence as semantic support."""

import json
from statistics import mean

from documind.evaluation.schemas import MODES, SIZES, EvaluationRun, Result


def pending_review(result: Result) -> bool:
    return not result.error and (
        result.correct is None or (not result.case.expected_refusal and result.supported is None)
    )


def validate_reviews(run: EvaluationRun) -> None:
    keys = [(result.case.id, result.chunk_size, result.retrieval_mode) for result in run.results]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate result keys; each case/configuration must be counted once.")
    for result in run.results:
        if (result.error or result.answer is None) and (result.correct or result.supported):
            raise ValueError(
                f"{result.case.id}: a failed request cannot be marked correct or supported."
            )
        if (
            result.answer
            and result.answer.refused
            and not result.case.expected_refusal
            and result.supported
        ):
            raise ValueError(
                f"{result.case.id}: a refusal cannot count as a supported factual answer."
            )


def render_report(run: EvaluationRun) -> str:
    validate_reviews(run)
    lines = [
        "# Retrieval evaluation",
        "",
        f"Started: {run.started_at.isoformat()}",
        "",
        "Latency measures the backend retrieval/generation pipeline, excluding ingestion,",
        "CLI pacing, and browser/API transport. Errors are counted separately, not as refusals.",
        "",
        "Hit@5 counts answerable cases where all expected evidence phrases occur on the",
        "expected page across the first five final retrieved passages (after gating/reranking).",
        "This is evidence coverage, not an LLM judgment or a pre-rerank candidate metric.",
        "",
        "| Chunk size | Retrieval | Recorded | Errors | Evidence hit@5 | Supported positives | Correct refusals | Mean successful ms | Review pending |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    scores = []
    for size in SIZES:
        for mode in MODES:
            rows = [
                row for row in run.results if row.chunk_size == size and row.retrieval_mode == mode
            ]
            positive = [row for row in rows if not row.case.expected_refusal]
            negative = [row for row in rows if row.case.expected_refusal]
            completed = [row for row in rows if row.error is None and row.answer is not None]
            hits = sum(row.hit_at_5 is True for row in positive)
            supported = sum(row.supported is True for row in positive)
            unreviewed = sum(pending_review(row) for row in rows)
            support_pending = sum(row.supported is None and not row.error for row in positive)
            refused = sum(
                row.answer is not None and row.error is None and row.answer.refused
                for row in negative
            )
            average = mean(row.latency_ms for row in completed) if completed else None
            support_text = f"{supported}/{len(positive)}" + (
                f" ({support_pending} pending)" if support_pending else ""
            )
            lines.append(
                f"| {size} | {mode} | {len(rows)}/15 | {sum(bool(row.error) for row in rows)} | {hits}/{len(positive)} | {support_text} | {refused}/{len(negative)} | {round(average) if average is not None else '—'} | {unreviewed} |"
            )
            scores.append(
                (
                    sum(row.correct is True for row in rows),
                    supported,
                    hits,
                    -(average if average is not None else float("inf")),
                    size,
                    mode,
                )
            )
    lines += [
        "",
        "Support and correctness require manual review of answers and their saved passages.",
        "Partial runs show observed denominators; compare configurations only after all 90 cases.",
        "",
    ]
    eligible = [score for score in scores if score[0] > 0 and score[1] > 0]
    if (
        len(run.results) == 90
        and not any(pending_review(row) for row in run.results)
        and eligible
    ):
        winner = max(eligible, key=lambda score: score[:4])
        lines += [
            f"Best observed configuration: **{winner[4]} / {winner[5]}**.",
            "Selection order: human-reviewed correct answers, supported positive answers,",
            "evidence coverage, then lower mean successful latency. Ties use listed order.",
        ]
    else:
        lines.append(
            "No winner selected: finish the run, review successful results, and establish supported correct answers first."
        )
    lines += [
        "",
        "## Recorded configuration",
        "",
        "```json",
    ]
    lines += [
        json.dumps(run.configuration, indent=2),
        "```",
        "",
        f"Document SHA-256: `{run.document_sha256}`",
        "",
        f"Question dataset SHA-256: `{run.questions_sha256}`",
        "",
        "This is one pass on a small demo dataset; results are not a general quality guarantee.",
        "",
    ]
    return "\n".join(lines)
