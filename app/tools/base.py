from dataclasses import dataclass
from typing import Any, Protocol


class ToolError(Exception):
    """Raised when a tool cannot do what it was asked.

    Recoverable on purpose: the message is fed back to the model so it can
    correct itself or explain, rather than failing the whole request. It is
    therefore written for a reader, and never carries internal detail.
    """


@dataclass(frozen=True)
class ToolSpec:
    """What the model is told about a tool.

    Vendor-neutral. Groq wants {type, function: {...}} and Anthropic wants
    {name, description, input_schema}; the client adapter translates so that
    neither shape reaches the service layer.
    """

    name: str
    description: str
    parameters: dict[str, Any]


class Tool(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str:
        """The only thing the model reads when deciding whether to call this.

        Prompt, not documentation: a vague description is a functional defect,
        because the tool is skipped when needed or called when it is not.
        """
        ...

    @property
    def parameters(self) -> dict[str, Any]:
        """JSON Schema. Constrains the shape of arguments, never their meaning."""
        ...

    def run(self, **kwargs: Any) -> str: ...
