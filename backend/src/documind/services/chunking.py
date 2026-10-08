"""Deterministic overlapping lexical chunks; sizes are not Gemini token counts."""

import re

from documind.schemas.documents import Chunk


def chunk_text(text: str, size: int, overlap: int, page: int | None = None) -> list[Chunk]:
    """Keep original whitespace while splitting Unicode words and punctuation."""
    if size <= 0 or not 0 <= overlap < size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")
    tokens = list(re.finditer(r"\w+|[^\w\s]", text))
    chunks = []
    for start in range(0, len(tokens), size - overlap):
        end = min(start + size, len(tokens))
        content = text[tokens[start].start() : tokens[end - 1].end()]
        chunks.append(Chunk(content, end - start, page))
        if end == len(tokens):
            break
    return chunks
