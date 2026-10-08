# Phase 2 review

Phase 2 implements document ingestion. Chat and answer generation remain in Phase 3.

## Follow an upload

1. `core/dependencies.py` resolves a seeded user from the bearer token using `Depends()`.
2. `api/documents.py` reads up to the file limit and calls ingestion.
3. `services/parsing.py` checks the filename, content type, byte signature, and
   size; it extracts UTF-8 text or PDF text with original page numbers.
4. `services/ingestion.py` checks the file hash before parsing and embedding.
5. `services/chunking.py` splits each page with overlap. Blank pages yield no chunks.
6. `integrations/embeddings.py` sends bounded batches to Gemini.
7. `repositories/documents.py` stores metadata and vectors in one transaction.
8. `schemas/documents.py` defines the response. New uploads return 201; duplicates
   return 200 with the original document ID. Both include a Location header.

Paths above are relative to `backend/src/documind/`.

## Why these choices

| Choice | Reason and practical limit |
| --- | --- |
| No `models.py` or ORM models | Application SQL is written in repositories; Alembic revisions define tables through `op.execute`. ORM classes would duplicate definitions without being used. Alembic itself does not require an ORM. |
| Pydantic schemas | Validate and describe API data; these are separate from database models. |
| SQLAlchemy only for Alembic | Supplies Alembic's PostgreSQL connection and transaction support. Application queries use asyncpg. |
| No background worker | Small uploads finish in the request. A queue and progress tracking belong to a later scale requirement. |
| No generic CRUD base class | Three document operations are clearer as explicit functions with visible permission filters. |
| Metadata reads call repositories directly | They have no additional business workflow; a service wrapper would only forward arguments. Ingestion uses a service because it coordinates multiple steps. |
| One owner field on documents | Chunk permissions join the parent document; there is no second ownership field to keep synchronized. Retrieval must retain that join in Phase 3. |
| Two seeded demo users | Allows testing document isolation without signup, OAuth, or extra `.env` credentials. These public demo tokens are not production authentication. |
| HTTPX for Gemini REST | One async HTTP client supports timeouts and offline tests. The direct REST integration avoids installing an additional SDK for this small API surface. |
| `gemini-embedding-2`, 768 dimensions | Uses the same Gemini key, supports multilingual text, and keeps vectors smaller than the default 3072 dimensions. Quality and latency still need the Phase 6 evaluation. See the [official embedding guide](https://ai.google.dev/gemini-api/docs/embeddings). |
| Local lexical tokenization | Unicode words and punctuation define deterministic chunks without a tokenizer download. Sizes 300/800 are **lexical tokens, not Gemini model tokens**; responses identify the unit. Native model-token budgets must be measured separately. |
| Page boundaries are preserved | Citations retain exact PDF page numbers. Chunks on short pages can be smaller than the selected size; overlap never crosses pages. |
| No vector index yet | Exact search is sufficient for a small demo corpus. The keyword GIN index supports the required hybrid search; approximate vector indexing can follow measured scale needs. |
| Deduplication includes configuration | Same owner + file hash + size + overlap + embedding model returns the same document. Changing chunk size intentionally creates a separate version for evaluation. |
| No original file storage | Parsed chunks and metadata are sufficient for Q&A. Original PDF download and in-browser highlighting are outside the current scope. |

## Dependencies added

`pypdf` extracts PDF text. `python-multipart` parses FastAPI file uploads. `httpx`
calls Gemini asynchronously. `pytest` and `pytest-asyncio` support offline tests.
`pydantic` v2 defines schemas and `pydantic-settings` provides validated configuration.
The settings object loads the root `.env`, lets environment variables override it,
validates database URLs and positive limits, and masks the Gemini key with `SecretStr`.
The model and vector dimensions are constrained to match the database migration.
The sample PDF is committed; reviewers do not need a PDF-generation dependency.

## Limits and failures

- Maximum 10 MB, 100 PDF pages, 500,000 extracted characters, and 200 chunks.
- UTF-8 text and text-based PDFs only. Password-protected and scanned-only PDFs
  produce clear errors; OCR is not installed.
- Gemini calls use batches of at most 32 chunks, 20-second HTTP timeouts, and
  at most three attempts for temporary failures. The embedding stage has a
  120-second overall deadline.
- A provider failure never reaches storage. Chunk insertion failure rolls back
  the new document. The uniqueness constraint handles concurrent duplicate uploads;
  concurrent requests can still incur duplicate embedding work before insertion.
- All document queries use the authenticated owner ID. An inaccessible ID returns
  the same 404 as a nonexistent ID. Client-supplied owner IDs are not accepted.
- Input failures return a stable `error.code` and safe `error.message`.

## Verification

54 offline tests passed: chunk boundaries/overlap, file validation, PDF page
extraction, malformed/encrypted PDFs, Gemini batching and bounded retries,
embedding validation, service failure handling, HTTP status/error behavior, and
Pydantic settings loading, environment precedence, validation, and secret masking.
Three opt-in pgvector tests cover permissions, concurrent deduplication, and rollback.
These three have not run in this workspace.

Lint, formatting, lockfile consistency, Compose configuration, OpenAPI generation,
and Alembic offline SQL generation pass. The three-page sample PDF was rendered
and visually inspected. It produces six chunks at size 300 and three at size 800.

Tests ran using an existing Python environment because installation from PyPI is
blocked here. A fresh locked install, live database migration, Docker startup, and
real Gemini request remain unverified. No retrieval or answer-quality results have
been measured yet.

## Migration commit fix

The standalone migration runner now uses an explicit engine transaction so the
initial schema lookup cannot leave migrations uncommitted. A regression test uses
real SQLite transactions with an adapter for the async transport and verifies both
seed and revision persistence, including a repeated upgrade. Readiness checks the
users table rather than only the database connection. Live pgvector verification
remains pending. The full suite passes in the existing verification environment;
the locked environment passed the migration regression alone, but its full suite
hangs during async executor teardown in this restricted workspace.
