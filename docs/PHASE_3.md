# Phase 3 review: retrieval and grounded answers

This phase adds document Q&A without adding services or Python dependencies.

## Request flow

`POST /api/v1/chat-messages` accepts a question, optional document/upload-date filters,
chunk size, retrieval mode, and streaming flag. Authentication supplies the owner;
the request cannot choose another user's identity.

1. Embed the question with Gemini embedding-2's question-answering query prefix.
2. Run owner-scoped cosine search. Hybrid modes also run English full-text search
   in parallel and merge ranks with reciprocal-rank fusion.
3. Drop candidates below the cosine threshold. No evidence means a fixed refusal
   without calling the generation model.
4. In `hybrid_rerank`, ask Gemini to score the remaining passages. Validate that the
   JSON ranking contains every supplied ID exactly once; keep scores at least 0.5.
5. Send up to five passages to Gemini with an instruction to use only context and
   treat document/question text as untrusted data. Stream native provider text.
6. Check numeric citations and require a citation in each paragraph. Invalid
   references replace the draft with a refusal. Return authoritative citation
   metadata from retrieved rows, never model-created filenames or document IDs.

## Files to review

| File | Responsibility |
| --- | --- |
| `schemas/chat.py` | Validated filters, retrieved evidence, citations, and final answer |
| `repositories/chunks.py` | Shared permission/filter clauses, vector and keyword queries, source lookup |
| `services/retrieval.py` | Rank fusion, cosine gate, optional reranker, context limit |
| `services/rag.py` | Isolated context prompt, citation validation, event flow, overall timeout |
| `integrations/llm.py` | Gemini REST generation/streaming and bounded model fallback |
| `integrations/reranker.py` | Structured relevance scores with exact source-ID validation |
| `integrations/embeddings.py` | Shared normalized document/query embeddings |
| `api/chat.py` | JSON for Swagger or SSE for browsers |
| `api/documents.py` | Owner-scoped full source passage endpoint |
| `core/config.py` | Pydantic v2 retrieval, model, output, and timeout defaults |

No new migration is needed: Phase 2 already stores vectors and generated full-text
columns. Exact vector search is adequate for the bounded demo corpus; an approximate
vector index is unnecessary at this scale. Ownership is stored once on documents
and checked through a join in every chunk query. All request values are SQL parameters.

## Generation and stream contract

The primary model is `gemini-3.5-flash-lite`; `gemini-3.8-flash` is the fallback.
The primary uses minimal thinking and the fallback low thinking, following the
[Gemini thinking controls](https://ai.google.dev/gemini-api/docs/generate-content/thinking).
Generation uses temperature 0.1, a 1,024-token output limit (including thought tokens), 30-second provider timeouts,
and a 120-second overall request timeout. Each provider operation attempts each
configured model once. These are request bounds, not the agent cost budget due in Phase 5.
A smaller primary reduces routine answer cost; actual latency needs measurement.

SSE events are `status`, `token`, `answer`, `error`, and `done`. `answer` contains the
final answer, citations, refusal flag, retrieval mode, model, and elapsed milliseconds.
The browser displays tokens as a draft and replaces them with `answer`. A failure
clears the draft and offers Retry. JSON requests consume the same event flow.

Fallback is permitted before the first token. After tokens have started, a failed or
unfinished provider stream returns an interruption error instead of appending a
second model's answer. A valid provider stream must finish with `STOP`.

## Deliberate limits

- The 0.45 cosine threshold and 0.5 reranker score cutoff are provisional, not measured
  probabilities. Phase 6 must test both chunk sizes and all three retrieval modes.
- Citation validation checks references and paragraph coverage, not semantic entailment.
  A cited hallucination is still possible; the prompt, threshold, reranking, and source
  display reduce risk without pretending to be a proof of correctness.
- Native streaming exposes draft text before final citation validation. The final event
  is authoritative. Consumers must follow the same replacement rule as the frontend.
- English full-text search is the keyword branch; embeddings can match other languages,
  but multilingual keyword behavior has not been evaluated.
- Upload-date filters refer to `documents.created_at`, not dates written inside a PDF.
- Reranking adds a Gemini request and may increase cost/latency. Its failure is explicit;
  it does not silently change the requested retrieval mode.
- No chat history is stored or passed to the model. Follow-up questions must stand alone.

Tests cover refusal without generation, rank fusion, shared filters, invalid rankings,
citation identity/coverage, native streaming interruption, fallback, HTTP/SSE contracts,
and authentication. Optional real PostgreSQL tests additionally cover owner, document,
date, and chunk-size filtering across both search branches.

Review with the sample walkthrough in the root README. Agent routing and tools remain
separate for Phase 5; evaluation and default selection remain for Phase 6.
