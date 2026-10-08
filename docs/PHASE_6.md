# Evaluation and handoff review

The evaluation runner is implemented. Actual provider results and final README
selection remain pending; adding a runner does not complete measured evaluation.

| File | Responsibility |
| --- | --- |
| `data/evaluation/questions.json` | Fifteen questions, expected answers, sections/pages, and evidence phrases |
| `evaluation/schemas.py` | Typed saved results and explicit human review fields |
| `evaluation/runner.py` | Validate gold evidence, ingest/reuse both variants, run once per case, checkpoint/resume |
| `evaluation/report.py` | Metrics, incomplete-review status, and declared configuration selection |
| `evaluation/__main__.py` | Run/report CLI, file options, pacing, failed-case retry |
| `services/rag.py` | Optional internal retrieval observer for recording the exact generation context |
| `tests/test_evaluation.py` | Gold evidence, top-five/page matching, failures, resume, review and reporting |

The observer does not alter public API responses or trigger an extra retrieval/model
call. The local CLI uses the existing owner-filtered backend pipeline, without adding
a service, frontend controls, dependency, credential, or grading model. Ingestion is
excluded from query timing; provider/network/model and reranking/repair time are included.

Settings, source-code hash, document hash, and dataset hash prevent incompatible
measurements from being resumed together. Credentials are excluded. Records checkpoint
after every case; human review fields survive resume. Explicit failed-case retry preserves
completed cases. A report with partial results/reviews does not claim a completed winner.

The user has confirmed frontend acceptance and a 151-test run including PostgreSQL.
The evaluation additions have offline coverage. Run the real comparison, review source
support and correctness, update the README with measured results, then perform the
reviewer's fresh-clone Docker startup and finalize repository/ZIP delivery.
