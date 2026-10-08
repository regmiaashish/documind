"""Chunk boundaries and overlap must preserve document evidence."""

from itertools import pairwise

import pytest

from documind.services.chunking import chunk_text


@pytest.mark.parametrize("size", [300, 800])
def test_sizes_and_overlap(size):
    text = " ".join(f"word{i}" for i in range(1800))
    chunks = chunk_text(text, size, 50, page=3)
    assert all(0 < chunk.token_count <= size and chunk.page == 3 for chunk in chunks)
    for left, right in pairwise(chunks):
        assert left.content.split()[-50:] == right.content.split()[:50]
    reconstructed = chunks[0].content.split()
    for chunk in chunks[1:]:
        reconstructed.extend(chunk.content.split()[50:])
    assert reconstructed == text.split()


def test_preserves_whitespace_and_unicode():
    text = "नेपाल policy.\n\nAnnual leave: 20 days."
    assert chunk_text(text, 300, 50)[0].content == text


@pytest.mark.parametrize("text", ["", "  \n\t"])
def test_empty_text_has_no_chunks(text):
    assert chunk_text(text, 300, 50) == []


@pytest.mark.parametrize("size,overlap", [(0, 0), (10, 10), (10, -1)])
def test_invalid_chunk_settings(size, overlap):
    with pytest.raises(ValueError):
        chunk_text("text", size, overlap)
