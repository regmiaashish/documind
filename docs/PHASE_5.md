# Phase 5 review: tools and code refinement

Ordinary document questions retain the RAG path. A small rule router selects tools
for explicit order-status or ticket requests. There is no agent framework, queue,
Redis dependency, or additional credential.

| File | Responsibility |
| --- | --- |
| `core/dependencies.py` | Inject database, authenticated user, embeddings, and LLM through `Depends()` |
| `core/db.py` | Create the shared asyncpg pool and close it on shutdown |
| `api/chat.py` | JSON/SSE HTTP boundary, five requests per minute |
| `api/actions.py` | Explicit confirmation of an owner-scoped stored draft |
| `core/rate_limit.py` | SlowAPI per-user quota and consistent 429 response |
| `core/budget.py` | Token/cost reservations before each agent provider attempt |
| `services/chat.py` | Route dispatch, whole-request deadline, safe terminal events |
| `services/router.py` | Small, reviewable intent rules |
| `services/agent.py` | Validated tools, bounded loop, read retries and parallel order reads |
| `schemas/tools.py` | Strict tool arguments, draft and ticket responses |
| `repositories/orders.py` | Parameterized, owner-scoped order lookup |
| `repositories/actions.py` | Draft creation and transactional confirmation |
| `migrations/versions/0003_tools.py` | Orders, pending actions, tickets, demo order seeds |
| `frontend/src/components/AnswerText.tsx` | Safe paragraph/list rendering |
| `frontend/src/components/TicketConfirmation.tsx` | Draft review and explicit confirmation |

## Decisions to review

- JSON and SSE share a five-per-minute quota. It uses authenticated identity, rather
  than the proxy address. Single-process memory storage resets when the API restarts.
- The router does not treat words such as “refund” as sufficient reason to run tools.
  Order lookup requires an order ID and status intent. The model cannot supply an
  owner, invent an order ID, or create a ticket from an order-only request.
- `create_ticket` inserts only a pending draft. Confirmation locks that row and inserts
  a ticket in the same transaction. A unique action ID makes repeated/concurrent
  confirmation idempotent. Foreign and expired drafts are rejected.
- Order answers use database fields directly. Agent document search uses the existing
  grounded answer path, retaining document/date/owner filters. It uses hybrid retrieval
  to avoid an extra unbudgeted reranker call.
- Up to three planning steps and three independent order reads per batch are allowed.
  Reads have a timeout and one transient retry after backoff. Writes are not retried
  automatically. Provider attempts, including fallback, reserve their own allowance.
- The token allowance deliberately overestimates input using UTF-8 bytes plus overhead.
  The cost allowance uses a configurable price ceiling. It is not actual usage/billing
  telemetry; larger context can hit the conservative cap earlier than provider limits.
- Current Gemini model defaults are preserved. Changing models is configurable and
  requires reviewing pricing and the budget ceiling; a stronger model alone cannot fix
  a citation parser error.
- Answers use safe React paragraphs/lists, without raw HTML or a Markdown dependency.
  Order/ticket questions work before upload. The interface distinguishes tool results
  from cited document answers.

## Verification and remaining work

All 151 backend tests passed in the user's local `RUN_DATABASE_TESTS=1 make test`
run, including owner boundaries, atomic uploads, concurrent confirmation, expired
drafts, and cascading document deletion. TypeScript/Vite build, stream tests, Ruff, frozen
dependency sync, lock validation, and Compose configuration pass.

Docker daemon access and provider networking are unavailable in this workspace, so
these results do not claim live Gemini, PostgreSQL, or browser verification. Run the
README workflow locally. The next phase is the measured 15-question comparison across
chunk sizes/retrieval modes, fresh-clone setup, and final evidence review. Citation
format checks are not semantic proof that every generated claim is supported.
