# Implementation and review phases

Each phase finishes with working behavior, verification evidence, and a short review
of its files. Review the phase before proceeding to the next one. Dependencies and
modules are added only when the phase needs them.

| Phase | Deliverable | Review criteria |
| --- | --- | --- |
| 1 — Foundation | Setup, locked Python dependencies, Docker, Alembic migrations, API readiness, README | Setup preserves the key; containers start; migrations are repeatable |
| 2 — Ingestion | PDF/text validation, parsing, overlapping chunks, Gemini embeddings, document tables and endpoints, sample document | Upload works; duplicate uploads create no duplicate chunks; invalid files return clear errors |
| 3 — Retrieval and answers | Vector and hybrid search, reranking, metadata/permission filters, SSE answers and citation checks | Answers cite evidence; weak context produces refusal; inaccessible documents never appear |
| 4 — Minimal frontend | React upload and chat page, citations, loading/error/retry states, frontend container | Browser upload → question → streamed cited answer works; layout works on mobile |
| 5 — Required agent | Router, document search, order lookup, confirmed ticket creation, budgets, timeouts and fallback | Ordinary questions use RAG; writes require confirmation; tool failure is honest |
| 6 — Evaluation and handoff | Required tests, 15 questions across two chunk sizes and three retrieval modes, real results, final README | Fresh-clone setup works exactly as documented; results justify the defaults |

## Design boundaries

- One backend, one frontend, one database; no queue, cache, or extra services.
- Routes use `/api/v1`, resource nouns, and HTTP methods; JSON fields use `snake_case`.
- Routes parse requests; services hold logic; repositories hold parameterized SQL.
- Gemini credentials stay on the backend. Only the API key is required in `.env`.
- Small document ingestion stays synchronous in this phase of the product.
- The UI uses one calm page: clear typography, restrained colors, readable spacing,
  a simple upload panel, and chat with clickable source references. No dashboard clutter.
- Evidence from PostgreSQL retrieval supplies answers; Gemini hosted file search
  does not replace the pgvector pipeline required by the task.

## Current status

Phases 1–5 are implemented. Phase 3 adds filtered retrieval, evidence gating,
streamed generation, and citations. Phase 4 adds the document/chat page and a static
frontend container. Read [Phase 2](PHASE_2.md), [Phase 3](PHASE_3.md), and
[Phase 4](PHASE_4.md), and [Phase 5](PHASE_5.md) for the files and decisions.

Current checks: all 151 baseline backend tests passed in the user's local run, including seven
PostgreSQL tests. Frontend stream tests, TypeScript/Vite build, and Compose configuration
validation also pass.
The user confirmed migration/startup recovery locally; new live Gemini, Docker, and
browser behavior remains unverified in this restricted workspace. The user subsequently
confirmed completion of the frontend walkthrough. The Phase 6 runner is implemented
with 14 additional offline tests: 158 pass here and seven database tests are skipped.
Measured provider results, answer review, and fresh-clone handoff remain pending.
See [Phase 6](PHASE_6.md) and the [evaluation guide](../data/evaluation/README.md).

## Backend layout

Backend files live inside `backend/`, alongside the separate `frontend/` folder:
`src/documind/`, `migrations/`, `alembic.ini`, `pyproject.toml`, `uv.lock`, `.venv`,
`Dockerfile`, and `.dockerignore`. The root Compose file coordinates services.
The shared Makefile, README, `.env`, and `.env.example` stay at the repository root.
`api/`, `core/`, `exceptions/`, `integrations/`, `repositories/`, `schemas/`, and
`services/` now contain code. Other layers will be added when needed; worker and
ORM model folders are unnecessary at present.
Alembic uses SQLAlchemy for migrations; application queries continue to use asyncpg.
