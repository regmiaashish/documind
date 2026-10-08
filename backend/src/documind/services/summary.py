"""Recognize explicit selected-document summaries and bound their context."""

import re

from documind.schemas.chat import RetrievedChunk

CONTEXT_CHARACTERS = 24_000


def is_document_summary(question: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:please\s+)?(?:summari[sz]e\s+(?:(?:this|the|my)\s+)?(?:pdf|document|file|handbook)"
            r"|(?:give me\s+)?(?:a\s+)?(?:(?:brief|short)\s+)?summary of\s+(?:this|the|my)\s+(?:pdf|document|file|handbook))"
            r"(?:\s+please)?[.!?]*",
            question.strip(),
            re.IGNORECASE,
        )
    )


def summary_context(chunks: list[RetrievedChunk], limit: int) -> list[RetrievedChunk]:
    if sum(len(chunk.content) for chunk in chunks) <= CONTEXT_CHARACTERS:
        return chunks
    count = min(max(limit, 2), len(chunks))
    indices = (
        sorted({round(index * (len(chunks) - 1) / (count - 1)) for index in range(count)})
        if count > 1
        else [0]
    )
    allowance = CONTEXT_CHARACTERS // len(indices)
    return [
        chunks[index].model_copy(update={"content": chunks[index].content[:allowance]})
        for index in indices
    ]
