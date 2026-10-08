"""Vector retrieval, reciprocal-rank fusion, and relevance-gated reranking."""

import asyncio
from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM
from documind.integrations.reranker import rerank
from documind.repositories.chunks import search_chunks, summary_chunks
from documind.schemas.chat import ChatRequest, RetrievalMode, RetrievedChunk
from documind.services.summary import is_document_summary, summary_context


def fuse_rankings(*rankings: list[RetrievedChunk]) -> list[RetrievedChunk]:
    scores: dict[UUID, float] = {}
    chunks: dict[UUID, RetrievedChunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking, start=1):
            chunks[chunk.chunk_id] = chunk
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0) + 1 / (60 + rank)
    return [chunks[key] for key in sorted(scores, key=lambda key: (-scores[key], str(key)))]


async def retrieve(
    pool: asyncpg.Pool,
    embeddings: GeminiEmbeddings,
    llm: GeminiLLM,
    owner_id: UUID,
    request: ChatRequest,
    mode: RetrievalMode,
) -> list[RetrievedChunk]:
    if (
        request.document_ids
        and len(request.document_ids) == 1
        and is_document_summary(request.question)
    ):
        chunks = await summary_chunks(pool, owner_id, request)
        return summary_context(chunks, settings.context_top_n) if chunks else []
    vector = await embeddings.embed_query(request.question)
    if mode == "vector":
        candidates = await search_chunks(pool, owner_id, request, vector)
    else:
        vector_hits, keyword_hits = await asyncio.gather(
            search_chunks(pool, owner_id, request, vector),
            search_chunks(pool, owner_id, request, vector, keyword=True),
        )
        candidates = fuse_rankings(vector_hits, keyword_hits)[: settings.retrieval_candidates]
    # RRF rank is not a probability. Exact keyword hits remain eligible for reranking
    # even when their embedding score is below the vector threshold.
    relevant = [
        chunk
        for chunk in candidates
        if chunk.similarity >= settings.similarity_threshold or chunk.keyword_match
    ]
    if relevant and mode == "hybrid_rerank":
        ranked = await rerank(llm, request.question, relevant)
        # Preserve an exact lexical hit when the provisional LLM cutoff rejects
        # every candidate. This keeps names and identifiers answerable while the
        # cosine threshold continues to gate pure vector retrieval.
        if ranked or not any(chunk.keyword_match for chunk in relevant):
            relevant = ranked
        else:
            relevant = [chunk for chunk in relevant if chunk.keyword_match]
    return relevant[: settings.context_top_n]
