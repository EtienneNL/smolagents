from __future__ import annotations

from dataclasses import dataclass

from .text_extractors import PageText


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    text: str
    page_number: int | None


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")
    if overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")
    if overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


def chunk_pages(pages: list[PageText], chunk_size: int, overlap: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    chunk_index = 0
    for page in pages:
        for chunk_text in _split_text(page.text, chunk_size, overlap):
            chunks.append(
                TextChunk(
                    chunk_index=chunk_index,
                    text=chunk_text,
                    page_number=page.page_number,
                )
            )
            chunk_index += 1
    return chunks
