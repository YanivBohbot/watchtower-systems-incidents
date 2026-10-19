"""Deterministic character chunking; page boundaries are preserved upstream."""


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> list[str]:
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    text = text.strip()
    result = []
    for start in range(0, len(text), size - overlap):
        chunk = text[start : start + size].strip()
        if chunk:
            result.append(chunk)
        if start + size >= len(text):
            break
    return result
