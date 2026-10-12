# DocuMind

A document Q&A application with cited answers, streamed responses, and an agent for
order lookups and confirmation-based support tickets. Built with FastAPI, React, and
PostgreSQL with pgvector.

**Live application:** [documind.aashish-regmi.com.np](https://documind.aashish-regmi.com.np)

**API docs:** [https://documind.aashish-regmi.com.np/docs](https://documind.aashish-regmi.com.np/docs)

## 1. Setup instructions

### Run from a clean clone

Install Docker with Docker Compose. From the repository root:

```bash
cp .env.example .env
```

Set `GEMINI_API_KEY` in `.env` to your key from
[Google AI Studio](https://aistudio.google.com/apikey). Then start the complete stack:

```bash
docker compose up --build
```

This starts the database, applies Alembic migrations, and starts the API and frontend.
Demo users and orders are seeded by migrations; no separate seed command is required.
The Gemini key stays on the backend and is never sent to the browser.

### Make commands

For local development, install Make and [uv](https://docs.astral.sh/uv/), then use:

```bash
make setup
# Add GEMINI_API_KEY to .env.
make up
```

`make setup` installs locked backend dependencies into `backend/.venv` and creates or
updates `.env` from `.env.example`, preserving existing values. A new environment leaves
the Gemini key blank for you to fill in. `make up` builds and starts containers in the
background, waiting for health checks.

After startup, run the evaluation when you are ready to measure quality:

```bash
make evaluate
make evaluation-report
```

These make real Gemini requests. Review saved answers before generating the final
comparison; see [evaluation results](#3-evaluation-results) for the current status and
instructions for a fresh run after code changes.

| Service | Local address |
| --- | --- |
| Frontend | [http://localhost:3000](http://localhost:3000) |
| Backend | [http://localhost:8000](http://localhost:8000) |
| Swagger | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Health | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) |
| PostgreSQL | `localhost:5432` |

### Reviewer walkthrough

1. Open the frontend and select **Alice · demo**.
2. Upload [`data/sample/handbook.pdf`](data/sample/handbook.pdf).
3. Ask **How many days of annual leave do employees receive?** Expect **20 days** with
   a citation. Expand the source to inspect the page, chunk and passage.
4. Ask **What is the yearly vacation allowance?** Expect the same supported answer.
5. Ask **What was Northstar's revenue in 2025?** Expect an explicit refusal because
   the document does not contain the answer.
6. Ask **What is the status of ORD-1001?** Expect a database-backed answer: shipped,
   delivery October 12, 2026. No document is required for this tool call.
7. Ask **Create a support ticket: my package arrived damaged.** Review and confirm the
   draft. A ticket is created only after confirmation.
8. Switch to **Bob · demo**. Alice's documents are unavailable; Bob's seeded order is
   `ORD-2001`. Use [`skyguard_comic.pdf`](data/sample/skyguard_comic.pdf) for another upload.

The sidebar supports owner-scoped deletion. Re-uploading the same file with the same
chunk settings reuses the existing document rather than creating duplicate chunks.
See the [frontend walkthrough](frontend/WALKTHROUGH.md) for positive, negative, isolation,
retry and deletion checks.

In Swagger, click **Authorize** and enter `dev-alice-key` without the `Bearer` prefix.
Use `dev-bob-key` for Bob. Upload through `POST /api/v1/documents`, copy the returned
`document_id`, then call `POST /api/v1/chat-messages`:

```json
{
  "question": "How many days of annual leave do employees receive?",
  "document_ids": ["replace-with-returned-document-uuid"],
  "chunk_size": 300,
  "retrieval_mode": "hybrid_rerank",
  "stream": false
}
```

Swagger uses JSON; the frontend uses streaming. Chat is limited to five requests per
minute per authenticated identity, shared across both formats. Published demo keys
represent shared demo identities, not private accounts. All users share the server's
Gemini project quota. Provider availability and free-tier eligibility depend on the
project; a new API key does not create a separate quota allowance.

### Checks and maintenance

```bash
make lint
make test
make test-web
make build-web

# Include real PostgreSQL integration tests:
docker compose up -d --wait db
RUN_DATABASE_TESTS=1 make test
```

Tests cover chunking, retrieval, citation handling, tool failures, provider fallback,
argument validation, budgets and rate limits. Database tests additionally cover
ownership, duplicate races, transactional rollback and ticket confirmation.

| Command | Purpose |
| --- | --- |
| `make migrate` | Apply pending Alembic migrations |
| `make restart` | Restart existing containers; use `make up` after code/config changes |
| `make stop` | Stop containers, retaining data |
| `make down` | Remove containers/network, retaining the database volume |
| `make logs` | Follow service logs |
| `make dev-web` | Run the frontend development server |

For startup or provider failures:

```bash
docker compose logs --no-color --tail=150 api
docker compose ps -a
```

## 2. Short architecture description

```text
React frontend → same-origin nginx /api proxy → FastAPI /api/v1
                                                  ├─ PostgreSQL + pgvector
                                                  └─ Gemini APIs
```

| Location | Responsibility |
| --- | --- |
| `backend/src/documind/api/` | HTTP routes and responses |
| `core/` | Pydantic settings, authentication/dependency injection, pool and budgets |
| `services/` | Ingestion, retrieval, grounded answers and agent orchestration |
| `repositories/` | Parameterized SQL with owner/document/date filters |
| `integrations/` | Gemini embedding, generation and reranking adapters |
| `schemas/`, `exceptions/` | Validated inputs/outputs and safe application errors |
| `backend/migrations/` | Alembic schema revisions and demo seeds |
| `frontend/` | React interface, streaming parser and frontend tests |
| `data/` | Sample documents, evaluation questions and recorded results |

Upload validates PDF/text input, extracts text, makes overlapping chunks, creates
embeddings and saves everything transactionally. One asyncpg pool per API process
provides one to five reusable connections and closes on shutdown.

Ordinary questions use RAG. Explicit order/ticket requests use a bounded agent with
`search_docs`, `get_order_status` and `create_ticket`. Owner identity comes from
FastAPI authentication dependencies, never model-generated arguments. Ticket drafts
expire after ten minutes; confirmation is owner-scoped and idempotent.

The review deployment uses a Google Cloud Compute Engine **e2-medium** VM with two
shared vCPUs, 4 GB RAM, Ubuntu 24.04 LTS and a 30 GB balanced disk, with HTTPS through
Caddy and Cloudflare. Gemini runs remotely, so no GPU or local model weights are needed.
This is a demo configuration, not a measured concurrency capacity guarantee.

## 3. Evaluation results

The [15-question dataset](data/evaluation/questions.json) includes expected answers
and the document sections/pages containing their evidence: twelve answerable questions
and three negative cases. The runner compares **300 and 800 lexical-token chunks**, each
with 50-token overlap, across vector, hybrid and hybrid-with-reranking retrieval:
**90 cases** in total.

**Current recorded results are incomplete.** The saved October 8 run contains thirteen
cases and predates subsequent retrieval fixes. It does not establish quality for the
current revision or a winning chunk size.

| Chunk size | Retrieval | Recorded | Evidence hit@5 | Supported answers | Mean successful response time |
| --- | --- | --- | --- | --- | --- |
| 300 | Vector | 13/15 | 12/12 positive cases | Not reviewed: 12 pending | 1,940 ms |
| 300 | Hybrid | 0/15 | Not measured | Not measured | Not measured |
| 300 | Hybrid + reranker | 0/15 | Not measured | Not measured | Not measured |
| 800 | Vector | 0/15 | Not measured | Not measured | Not measured |
| 800 | Hybrid | 0/15 | Not measured | Not measured | Not measured |
| 800 | Hybrid + reranker | 0/15 | Not measured | Not measured | Not measured |

The recorded vector cases had no request errors and one observed refusal out of one
negative case. All thirteen responses still require correctness review. A pending
support review is not a failed answer, and retrieval hits do not prove answer support.

- **Evidence hit@5:** expected evidence phrases appear on the expected page across the
  first five final passages. This measures final-context coverage after filtering and
  reranking, rather than the original candidate ranking.
- **Supported answers:** human review confirms every factual claim is supported by
  its cited passages.
- **Response time:** backend retrieval and generation duration, including reranking
  and citation repair, excluding upload, CLI pacing and browser/network transport.

**Current default:** 300-token chunks with hybrid reranking. Smaller passages keep
context focused and make citations easier to inspect; reranking judges paraphrased
meaning. This is a provisional engineering choice, not an evaluation-proven winner.
800-token chunks may preserve more surrounding context at the cost of larger prompts.
The final choice must follow the completed, reviewed comparison.

Because pipeline code changed after the saved run, use new result/report files:

```bash
make evaluate EVAL_ARGS="--delay 5 --output data/evaluation/results-v2.json"
# Review supported/correct fields in results-v2.json against saved passages.
make evaluation-report EVAL_ARGS="--input data/evaluation/results-v2.json --output data/evaluation/report-v2.md"
```

Then replace the table above with the complete reviewed results and explain the winning
configuration. The [evaluation guide](data/evaluation/README.md) documents review and
resume rules. [Raw saved results](data/evaluation/results.json) and the
[existing report](data/evaluation/report.md) remain available for inspection.

## 4. Key technical decisions and tradeoffs

| Decision | Reason and tradeoff |
| --- | --- |
| asyncpg SQL + Alembic, without ORM `models.py` | Ownership and transactions are explicit. Migrations own the schema and Pydantic validates API data; unused ORM models would duplicate that description. Schema/query changes must be kept consistent. |
| Synchronous ingestion | Keeps a small application easy to run without a worker/queue. Large uploads hold the request open. |
| Gemini embedding-2, normalized 768-dimensional vectors | Remote multilingual semantic embeddings avoid local model infrastructure; 768 dimensions bound storage. Quality must be measured on the supplied corpus, and provider quota/network availability are dependencies. |
| Small primary model with fallback | Defaults are `gemini-3.5-flash-lite` and `gemini-3.8-flash`. This limits routine generation cost; fallback adds latency and shares provider availability/quota constraints. |
| Vector, hybrid and reranked retrieval | Cosine search handles meaning; English full-text search adds lexical evidence. Reranking judges up to twelve scoped candidates before a cosine cutoff can discard paraphrases, at the cost of another model call. |
| Separate relevance gates | Vector mode uses the cosine threshold; hybrid also admits full-text hits. Reranked mode uses a relevance cutoff of 0.5 and respects rejection. Thresholds remain provisional until evaluated. |
| Citations and bounded repair | Prompts require context-only answers and citation markers. One repair handles incomplete references. Structural validation cannot prove every claim, so human-supported-answer evaluation remains necessary. |
| Plain RAG before agent routing | Ordinary document questions avoid unnecessary tool planning. Explicit tool requests get three planning steps, validated arguments, bounded timeouts/retry and estimated token/cost budgets. |
| Explicit confirmation for writes | The model prepares a draft; the user authorizes ticket creation. Database locking and uniqueness prevent duplicate confirmation writes. |
| Lightweight Compose packaging | Multi-stage Python slim and frontend nginx images keep deployment simple. Each service has its own build context and `.dockerignore`. A single VM is inexpensive operationally but has no high availability. |

Document content and questions are untrusted data. They cannot override system rules,
select another owner or authorize writes. SQL applies owner, document/date, embedding
model and chunk-size filters. Generation uses low temperature and refuses when evidence
is absent. Streams show drafts; the validated final response replaces them.

Summary requests use bounded passages from the selected document, rather than searching
for the word "summary". Large-document summaries sample passages and explicitly describe
that scope. English lexical search is more limited than multilingual embeddings. Chunk
sizes count lexical tokens rather than the provider's exact tokenizer.

## 5. What I would improve next

1. Complete the reviewed evaluation, tune relevance gates from positive/negative cases,
   and extend the corpus with paraphrases and more diverse documents.
2. Add private authentication and per-account provider/storage quotas before opening
   beyond shared demo users. The current in-memory rate limiter is process-local.
3. Add background ingestion with progress reporting only when document sizes or measured
   traffic justify a worker; add OCR if scanned PDFs become a real requirement.
4. Add operational checks for provider failures, request latency, bounded logs and
   restart/backup recovery. Benchmark the VM before claiming production capacity.
5. Consider vector indexes and larger deployment resources when corpus size and measured
   query latency justify them.

The priority is verified answer quality and reproducible startup before additional
infrastructure or features.
