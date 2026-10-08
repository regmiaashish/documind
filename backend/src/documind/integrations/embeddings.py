"""Gemini REST embeddings with bounded batches, timeout, and safe errors."""

import asyncio
import math

import httpx

from documind.core.config import settings
from documind.exceptions import AppError


class GeminiEmbeddings:
    def __init__(self, client: httpx.AsyncClient, api_key: str):
        self.client = client
        self.api_key = api_key

    async def embed_documents(self, texts: list[str], title: str) -> list[list[float]]:
        return await self._embed([f"title: {title} | text: {text}" for text in texts])

    async def embed_query(self, question: str) -> list[float]:
        # Embedding 2 uses text prefixes rather than the older taskType field.
        return (await self._embed([f"task: question answering | query: {question}"]))[0]

    async def _embed(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise AppError(503, "missing_api_key", "Add GEMINI_API_KEY to .env and run make up.")
        vectors = []
        for start in range(0, len(texts), 32):
            batch = texts[start : start + 32]
            payload = {
                "requests": [
                    {
                        "model": f"models/{settings.embedding_model}",
                        "content": {"parts": [{"text": text}]},
                        "outputDimensionality": settings.embedding_dimensions,
                    }
                    for text in batch
                ]
            }
            response = await self._request(payload)
            try:
                embeddings = response.json()["embeddings"]
                if len(embeddings) != len(batch):
                    raise ValueError("Embedding count mismatch")
                for embedding in embeddings:
                    values = [float(value) for value in embedding["values"]]
                    if len(values) != settings.embedding_dimensions or not all(
                        map(math.isfinite, values)
                    ):
                        raise ValueError("Invalid embedding dimensions or values")
                    norm = math.sqrt(sum(value * value for value in values))
                    if norm == 0 or not math.isfinite(norm):
                        raise ValueError("Invalid embedding norm")
                    vectors.append([value / norm for value in values])
            except (KeyError, TypeError, ValueError, OverflowError) as error:
                raise AppError(
                    502, "invalid_embeddings", "Gemini returned invalid embeddings."
                ) from error
        return vectors

    async def _request(self, payload: dict) -> httpx.Response:
        for attempt in range(3):
            try:
                response = await self.client.post(
                    f"{settings.gemini_base_url}/models/{settings.embedding_model}:batchEmbedContents",
                    headers={"x-goog-api-key": self.api_key},
                    json=payload,
                    timeout=20,
                )
            except httpx.TransportError:
                response = None
            if response is not None:
                if response.is_success:
                    return response
                if response.status_code not in (429, 500, 502, 503, 504):
                    raise AppError(
                        502,
                        "embedding_rejected",
                        "Gemini rejected the upload. Check the API key and file.",
                    )
            if attempt < 2:
                await asyncio.sleep(0.5 * (2**attempt))
        raise AppError(
            503,
            "embedding_unavailable",
            "Gemini is unavailable or rate limited. Check GEMINI_API_KEY and quota, then retry.",
        )
