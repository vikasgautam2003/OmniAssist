
BOUNDARIES = ("\n\n", "\n", ". ", " ")


BOUNDARY_WINDOW = 0.8


def _cut_at(text: str, start: int, end: int) -> int:
    """Pull `end` back to the best natural boundary, or leave it alone."""
    floor = start + int((end - start) * BOUNDARY_WINDOW)

    for marker in BOUNDARIES:
        found = text.rfind(marker, floor, end)
        if found != -1:

            return found + len(marker)

    return end


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, preferring natural boundaries.

    Keyword-only on purpose: chunk_text(body, 150, 1000) type-checks perfectly
    and silently produces garbage, so the arguments are made unspellable in the
    wrong order.
    """
    if size <= 0:
        raise ValueError("Chunk size must be greater than 0.")
    if overlap < 0:
        raise ValueError("Chunk overlap must be non-negative.")
    if overlap >= size:
        raise ValueError("Chunk overlap must be less than chunk size.")

    chunks: list[str] = []
    start = 0
    length = len(text)

    while start < length:
        end = min(start + size, length)

        if end < length:
            end = _cut_at(text, start, end)

        piece = text[start:end].strip()
        if piece:

            chunks.append(piece)

        if end >= length:
            break


        start = max(end - overlap, start + 1)

    return chunks
