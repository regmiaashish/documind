# Submission readiness review

**Verdict: the implementation is ready for local acceptance testing, but the submission
is not complete.** The assignment explicitly requires measured evaluation results.
Expected answers and mocked tests do not satisfy that requirement.

## Assignment criteria

| Criterion or deliverable | Evidence | Status |
| --- | --- | --- |
| FastAPI, PostgreSQL/pgvector, React | Backend, migrations, frontend | Implemented |
| Upload PDF/text, validation, overlap, embeddings, deduplication | Ingestion services and tests | Implemented; live upload needs acceptance testing |
| Vector, hybrid, reranking, relevance handling, citations | Retrieval and answer services | Implemented; quality/defaults not measured |
| Document/date/owner filters | Owner-scoped SQL and regression tests | PostgreSQL tests passed locally |
| Three tools and router | Document search, order lookup, pending ticket drafts | Implemented; live provider/tool flow pending |
| Confirmation before ticket writes | Confirmation endpoint, row lock, unique action ID, frontend review | PostgreSQL concurrency/expiry tests passed; browser acceptance pending |
| Steps, token/cost allowance, timeout/retry, argument validation | Agent guardrails and failure tests | Offline verified; cost is a conservative estimate |
| Fallback, streaming, cheap primary, parallel reads | Gemini adapter, SSE, order batches | Offline verified; live behavior pending |
| Single-page UI, source expansion, errors/retry | Frontend components and walkthrough | Build passes; browser acceptance pending |
| One-command Docker startup | Compose health dependencies and API migration startup | Config validated; clean-machine run pending |
| Environment template, samples, seed data | `.env.example`, handbook/comic, seeded users/orders | Present |
| Chunking, retrieval, tool-failure tests | 151 passing backend tests | Full suite, including seven PostgreSQL tests, passed locally |
| Fifteen questions with expected answers and sections | `data/evaluation/questions.json` and walkthrough | Written and validated against the sample PDF |
| Results for both chunk sizes, retrieval comparison, supported answers, mean latency | Resumable evaluation runner and report command | Runner implemented; live results/review pending |
| README architecture, setup, decisions, winning configuration | Root README and review documents | Setup present; evaluation and final justification incomplete |
| Repository/ZIP delivery and reviewer access | Not verifiable from this workspace | Pending verification |

Document deletion is also implemented: an authenticated owner can delete a document
and its cascading chunks using `DELETE /api/v1/documents/{id}`. The sidebar exposes a
one-click trash button, updates selection/history, and preserves the card on failure.
The database cascade/ownership test passed in the user's local database run.

On October 8, 2026, the user ran `RUN_DATABASE_TESTS=1 make test`: all 151 tests
passed in 2.18 seconds. Fourteen Alembic configuration deprecation warnings were
reported; `path_separator = os` has since been added to address their stated cause.
After adding the evaluation runner, 158 tests passed offline here; the seven database
tests were skipped in this environment. The user also confirmed the frontend walkthrough.

## Work required before submission

1. The user confirmed satisfaction with the completed frontend walkthrough. Rebuild
   and repeat smoke checks if subsequent application behavior changes.
2. The full PostgreSQL test run has passed. Complete browser checks for migrated
   startup and retained documents across restarts.
3. Run `make evaluate`, review the saved answers/passages, and run `make evaluation-report`.
   This compares the fifteen cases at 300/800 chunk sizes across all three retrieval
   modes. See `data/evaluation/README.md` for metric definitions and resume behavior.
4. Review the provisional relevance thresholds and keyword fallback using positive
   and negative results. Currently lexical matches can bypass the cosine gate and
   remain eligible when the reranker rejects every candidate. This needs evidence
   before treating refusal behavior as reliable.
5. Put the measured results, justified winning chunk/retrieval configuration, embedding
   quality/cost/dimension/language tradeoffs, and future improvements in the README.
   Do not replace measured quality with a passing unit-test count.
6. Test the reviewer's exact fresh-clone flow: copy `.env.example`, add the key, run
   `docker compose up --build`, upload, ask, inspect citations, and call an order tool.
   Verify the final repository or ZIP includes samples and excludes actual secrets.

Docker daemon and provider network access are unavailable here. This review therefore
does not claim end-to-end acceptance, current provider billing measurements, or a
completed clean-machine run. No repository invitation or submission has been sent.
