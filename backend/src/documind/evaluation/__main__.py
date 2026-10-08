"""CLI entry point: generate resumable measurements or report reviewed results."""

import argparse
import asyncio
from pathlib import Path
from uuid import UUID

import asyncpg

from documind.evaluation.report import render_report
from documind.evaluation.runner import run_evaluation
from documind.evaluation.schemas import EvaluationRun
from documind.exceptions import AppError

ROOT = Path(__file__).resolve().parents[4]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate 15 document questions across six configurations."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "run", help="Uses PostgreSQL and Gemini; saves progress and resumes automatically."
    )
    run.add_argument("--document", type=Path, default=ROOT / "data/sample/handbook.pdf")
    run.add_argument("--questions", type=Path, default=ROOT / "data/evaluation/questions.json")
    run.add_argument("--output", type=Path, default=ROOT / "data/evaluation/results.json")
    run.add_argument("--user", choices=["alice", "bob"], default="alice")
    run.add_argument(
        "--delay", type=float, default=2, help="Seconds between cases; raise for provider quotas."
    )
    run.add_argument("--retry-failed", action="store_true")
    report = commands.add_parser("report", help="Creates a Markdown report without calling Gemini.")
    report.add_argument("--input", type=Path, default=ROOT / "data/evaluation/results.json")
    report.add_argument("--output", type=Path, default=ROOT / "data/evaluation/report.md")
    args = parser.parse_args()
    try:
        if args.command == "run":
            if args.delay < 0:
                parser.error("--delay must be nonnegative")
            asyncio.run(
                run_evaluation(
                    args.document,
                    args.questions,
                    args.output,
                    UUID(int=1 if args.user == "alice" else 2),
                    args.delay,
                    args.retry_failed,
                )
            )
        else:
            if args.input.resolve() == args.output.resolve():
                raise ValueError("Report output must differ from the saved JSON input.")
            result = render_report(EvaluationRun.model_validate_json(args.input.read_text()))
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(result, encoding="utf-8")
            print(f"Report written to {args.output}")
    except (ValueError, OSError) as error:
        parser.exit(1, f"Evaluation failed: {error}\n")
    except AppError as error:
        parser.exit(1, f"Evaluation failed: {error.message}\n")
    except asyncpg.PostgresError:
        parser.exit(
            1,
            "Evaluation failed: PostgreSQL is unavailable or migrations are missing. Run make migrate.\n",
        )


if __name__ == "__main__":
    main()
