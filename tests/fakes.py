import hashlib
import math
from collections.abc import Iterator, Sequence

from app.clients.base import StreamEvent
from app.domain import Message, ToolCall
from app.tools.base import ToolSpec


class FakeLLMClient:
    """A scriptable stand-in for a provider.

    `replies` is consumed one entry per model turn, so a test can script
    "call this tool, then answer" without a network or a key.
    """

    def __init__(
        self,
        reply: str = "fake reply",
        tool_calls: Sequence[Sequence[ToolCall]] = (),
    ) -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []
        self.tools_offered: list[list[ToolSpec]] = []
        self._scripted = [tuple(batch) for batch in tool_calls]
        self._turn = 0

    def stream_chat(
        self, messages: list[Message], tools: Sequence[ToolSpec] = ()
    ) -> Iterator[StreamEvent]:
        # Recorded eagerly: the caller must be able to assert what was sent
        # even if the stream is never consumed.
        self.calls.append(list(messages))
        self.tools_offered.append(list(tools))
        turn = self._turn
        self._turn += 1
        return self._stream(turn)

    def _stream(self, turn: int) -> Iterator[StreamEvent]:
        if turn < len(self._scripted):
            yield StreamEvent(tool_calls=self._scripted[turn])
            return

        size = 4
        for i in range(0, len(self.reply), size):
            yield StreamEvent(text=self.reply[i : i + size])


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
