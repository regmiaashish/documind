# Retrieval evaluation

Started: 2026-10-08T06:02:04.522939+00:00

Latency measures the backend retrieval/generation pipeline, excluding ingestion,
CLI pacing, and browser/API transport. Errors are counted separately, not as refusals.

Hit@5 counts answerable cases where all expected evidence phrases occur on the
expected page across the first five final retrieved passages (after gating/reranking).
This is evidence coverage, not an LLM judgment or a pre-rerank candidate metric.

| Chunk size | Retrieval | Recorded | Errors | Evidence hit@5 | Supported positives | Correct refusals | Mean successful ms | Review pending |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 300 | vector | 13/15 | 0 | 12/12 | 0/12 (12 pending) | 1/1 | 1940 | 13 |
| 300 | hybrid | 0/15 | 0 | 0/0 | 0/0 | 0/0 | — | 0 |
| 300 | hybrid_rerank | 0/15 | 0 | 0/0 | 0/0 | 0/0 | — | 0 |
| 800 | vector | 0/15 | 0 | 0/0 | 0/0 | 0/0 | — | 0 |
| 800 | hybrid | 0/15 | 0 | 0/0 | 0/0 | 0/0 | — | 0 |
| 800 | hybrid_rerank | 0/15 | 0 | 0/0 | 0/0 | 0/0 | — | 0 |

Support and correctness require manual review of answers and their saved passages.
Partial runs show observed denominators; compare configurations only after all 90 cases.

No winner selected: finish the run, review successful results, and establish supported correct answers first.

## Recorded configuration

```json
{
  "embedding_model": "gemini-embedding-2",
  "embedding_dimensions": 768,
  "chunk_overlap": 50,
  "max_chunks": 200,
  "llm_primary_model": "gemini-3.5-flash-lite",
  "llm_fallback_model": "gemini-3.8-flash",
  "llm_max_output_tokens": 1024,
  "retrieval_candidates": 12,
  "context_top_n": 5,
  "similarity_threshold": 0.45,
  "request_timeout_seconds": 120,
  "owner_id": "00000000-0000-0000-0000-000000000001",
  "pipeline_sha256": "e3aeeb2977fdbe7c0d5d710d78c9b16e1af591e03a5c3544a08f128182a89912"
}
```

Document SHA-256: `b5b4eb4fee9fb9aee09427f368559275808aca33e66881207bafdfa609226ebf`

Question dataset SHA-256: `84161698d1b55b9edacefb62da930a25ef6d1c3944d102f63e65228ed5ccf221`

This is one pass on a small demo dataset; results are not a general quality guarantee.
