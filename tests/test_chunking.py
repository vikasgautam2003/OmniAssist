from itertools import pairwise

import pytest

from app.services.chunking import chunk_text


def test_text_shorter_than_the_limit_is_one_chunk() -> None:
    assert chunk_text("a short note", size=100, overlap=10) == ["a short note"]


def test_empty_and_whitespace_only_text_yields_nothing() -> None:
    """An empty chunk becomes an embedding of nothing, which would match
    queries at random once stored in the index."""
    assert chunk_text("", size=50, overlap=10) == []
    assert chunk_text("   \n\n  \t ", size=50, overlap=10) == []


def test_long_text_is_split_and_no_chunk_exceeds_the_limit() -> None:
    text = " ".join(f"word{i:03d}" for i in range(200))
    chunks = chunk_text(text, size=100, overlap=20)

    assert len(chunks) > 1
    assert all(len(c) <= 100 for c in chunks)


def _shared_run(first: str, second: str) -> int:
    """Length of the longest tail of `first` that is also a head of `second`."""
    for n in range(min(len(first), len(second)), 0, -1):
        if first[-n:] == second[:n]:
            return n
    return 0


def test_consecutive_chunks_share_text() -> None:
    text = " ".join(f"w{i:02d}" for i in range(60))
    chunks = chunk_text(text, size=60, overlap=15)

    for first, second in pairwise(chunks):
        assert _shared_run(first, second) > 0, (
            f"no overlap between {first!r} and {second!r}"
        )


def test_a_paragraph_break_is_preferred_over_a_nearer_space() -> None:
    """A space sitting closer to the hard limit must not beat a clean
    paragraph boundary a few characters earlier."""
    text = "A" * 40 + "\n\n" + "B" * 8 + " " + "C" * 40
    chunks = chunk_text(text, size=52, overlap=5)

    assert chunks[0] == "A" * 40


def test_overlap_not_smaller_than_size_is_rejected() -> None:
    """Were this allowed, start would never advance and the call would hang."""
    with pytest.raises(ValueError):
        chunk_text("some text", size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("some text", size=100, overlap=150)


def test_no_text_is_lost() -> None:
    """The regression that mattered: a boundary pulling `end` backwards once
    opened a gap no chunk covered, and the text in it was dropped silently.
    The long unbroken run is what triggers it -- a URL, hash or base64 blob
    does the same in a real document."""
    text = "one two " + "Z" * 45 + " three four five"
    chunks = chunk_text(text, size=50, overlap=10)

    assert "".join(chunks).count("Z") >= text.count("Z")
    for word in ("one", "two", "three", "four", "five"):
        assert any(word in c for c in chunks), f"{word!r} was lost"


def test_a_huge_overlap_still_terminates() -> None:
    """overlap < size passes the guard, yet the boundary window can pull `end`
    back far enough that start - overlap moves backwards. The clamp is what
    stops that becoming an infinite loop."""
    text = " ".join(f"word{i:03d}" for i in range(80))
    chunks = chunk_text(text, size=100, overlap=95)

    assert chunks
