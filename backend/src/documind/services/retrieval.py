"""Vector retrieval, reciprocal-rank fusion, and relevance-gated reranking."""

import asyncio
import logging
from uuid import UUID

import asyncpg

from documind.core.config import settings
from documind.integrations.embeddings import GeminiEmbeddings
from documind.integrations.llm import GeminiLLM
from documind.integrations.reranker import rerank
from documind.repositories.chunks import search_chunks, summary_chunks
from documind.schemas.chat import ChatRequest, RetrievalMode, RetrievedChunk
from documind.services.summary import is_document_summary, summary_context

logger = logging.getLogger(__name__)


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
    # The reranker can recognize paraphrases below the cosine cutoff. Its bounded
    # candidate set remains owner-scoped; its relevance decision is final.
    if mode == "hybrid_rerank":
        relevant = await rerank(llm, request.question, candidates) if candidates else []
    else:
        relevant = [
            chunk
            for chunk in candidates
            if chunk.similarity >= settings.similarity_threshold or chunk.keyword_match
        ]
    logger.info(
        "Retrieval mode=%s candidates=%d eligible=%d selected=%d scores=%s",
        mode,
        len(candidates),
        len(relevant),
        min(len(relevant), settings.context_top_n),
        [
            (str(chunk.chunk_id), round(chunk.similarity, 3), chunk.keyword_match)
            for chunk in candidates
        ],
    )
    return relevant[: settings.context_top_n]
