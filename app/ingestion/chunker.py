"""
Semantic chunker with ~15% overlap.

Splits text on sentence boundaries, accumulates sentences up to
*target_size* characters, and overlaps consecutive chunks by
*overlap_ratio* of the target size.
"""

import re


def chunk_text(text: str, target_size: int = 500, overlap_ratio: float = 0.15) -> list[str]:
    if not text or not text.strip():
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        return [text.strip()]

    if len(sentences) == 1:
        return sentences

    overlap_chars = int(target_size * overlap_ratio)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        add_space = " " if current else ""
        if len(current) + len(add_space) + len(sentence) <= target_size:
            current += add_space + sentence
        else:
            if current.strip():
                chunks.append(current.strip())
            if overlap_chars > 0 and len(current) > overlap_chars:
                current = current[-overlap_chars:] + " " + sentence
            else:
                current = sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks
