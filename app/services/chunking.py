# Tried in order: a paragraph break beats a line break beats a sentence end
# beats a plain space. The first one found wins, so a clean paragraph boundary
# is preferred even when a space sits closer to the hard limit.
BOUNDARIES = ("\n\n", "\n", ". ", " ")

# A boundary is only worth taking in the last fifth of the window. Searching
# the whole window lets one early space produce a tiny chunk -- a long URL,
# hash or run of CJK text is enough to trigger it.
BOUNDARY_WINDOW = 0.8


def _cut_at(text: str, start: int, end: int) -> int:
    """Pull `end` back to the best natural boundary, or leave it alone."""
    floor = start + int((end - start) * BOUNDARY_WINDOW)

    for marker in BOUNDARIES:
        found = text.rfind(marker, floor, end)
        if found != -1:
            # Cut after the marker so the sentence or paragraph stays whole.
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
            # A whitespace-only run is skipped rather than stored: an empty
            # chunk becomes an embedding of nothing, which matches queries at
            # random once it is in the index.
            chunks.append(piece)

        if end >= length:
            break

        # Relative to where this chunk actually ended, never to where it was
        # assumed to end -- otherwise the boundary adjustment opens a gap and
        # the text in it is dropped. The clamp guarantees forward progress:
        # the overlap < size guard alone still allows start to move backwards
        # once the window has pulled `end` in, which would never terminate.
        start = max(end - overlap, start + 1)

    return chunks
