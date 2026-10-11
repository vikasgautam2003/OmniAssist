import hashlib
import math
from collections.abc import Iterator

from app.domain import Message


class FakeLLMClient:
    def __init__(self, reply: str = "fake reply") -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []

    def chat(self, messages: list[Message]) -> str:
        self.calls.append(messages)
        return self.reply

    def stream_chat(self, messages: list[Message]) -> Iterator[str]:
        self.calls.append(messages)
        return self._stream()

    def _stream(self) -> Iterator[str]:
        size = 4

        for i in range(0, len(self.reply), size):
            yield self.reply[i : i + size]


def make_pdf(text: str) -> bytes:
    """Build a minimal single-page PDF containing `text`.

    Hand-assembled rather than generated with reportlab: a whole PDF-writing
    library is a lot of dependency for a test fixture, and writing it out makes
    the structure visible -- objects, an xref table of byte offsets, a trailer.
    """
    content = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET".encode()

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []

    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(number).encode() + b" 0 obj\n" + body + b"\nendobj\n"

    xref_at = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"

    for offset in offsets:
        out += b"%010d 00000 n \n" % offset

    out += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\n"
    out += b"startxref\n" + str(xref_at).encode() + b"\n%%EOF\n"

    return bytes(out)


class FakeEmbedder:
    """Deterministic vectors from a hash: no model, no download, no network."""

    def __init__(self, dimensions: int = 8) -> None:
        self._dimensions = dimensions

    @property
    def model_id(self) -> str:
        return "fake"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.shake_256(text.encode()).digest(self._dimensions)
        raw = [byte / 255 for byte in digest]
        length = math.sqrt(sum(value * value for value in raw)) or 1.0
        return [value / length for value in raw]
