import uuid
from typing import Any

import pytest

from app.domain import ToolCall
from app.tools.base import ToolContext, ToolError
from app.tools.calculator import Calculator
from app.tools.registry import ToolRegistry


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry([Calculator()])


CONTEXT = ToolContext(user_id=uuid.uuid4())


def call(name: str, arguments: str) -> ToolCall:
    return ToolCall(id="c1", name=name, arguments=arguments)


# ---------------------------------------------------------------- calculator
def test_it_calculates() -> None:
    assert Calculator().run(CONTEXT, expression="(19 * 43) / 7") == "116.71428571428571"


def test_whole_results_are_not_shown_as_floats() -> None:
    assert Calculator().run(CONTEXT, expression="2 + 2") == "4"


def test_division_by_zero_is_refused() -> None:
    with pytest.raises(ToolError, match="zero"):
        Calculator().run(CONTEXT, expression="10 / 0")


def test_an_exponent_bomb_is_refused() -> None:
    """2 ** 10_000_000 is valid arithmetic that hangs the process and
    exhausts memory. Bounding it is cheaper than a timeout."""
    with pytest.raises(ToolError, match="exponent"):
        Calculator().run(CONTEXT, expression="2 ** 99999999")


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("ls")',
        'open("/etc/passwd").read()',
        "[].__class__.__base__.__subclasses__()",
        "lambda: 1",
    ],
)
def test_code_is_refused_not_executed(expression: str) -> None:
    """The model's input can come from an uploaded document, so eval() here
    would be remote code execution. Only arithmetic nodes are evaluated."""
    with pytest.raises(ToolError):
        Calculator().run(CONTEXT, expression=expression)


def test_an_empty_expression_is_refused() -> None:
    with pytest.raises(ToolError):
        Calculator().run(CONTEXT, expression="   ")


# ---------------------------------------------------------------- registry
def test_the_catalogue_describes_each_tool(registry: ToolRegistry) -> None:
    spec = registry.catalogue()[0]

    assert spec.name == "calculate"
    assert spec.parameters["required"] == ["expression"]
    assert spec.description, "the description is the prompt; it cannot be empty"


def test_a_successful_call_returns_the_result(registry: ToolRegistry) -> None:
    assert registry.run(call("calculate", '{"expression": "6 * 7"}'), CONTEXT) == "42"


def test_an_unknown_tool_is_reported_not_raised(registry: ToolRegistry) -> None:
    """Every failure becomes text the model can read and recover from."""
    assert "No tool named" in registry.run(call("nonsense", "{}"), CONTEXT)


def test_malformed_arguments_are_reported(registry: ToolRegistry) -> None:
    assert "not valid JSON" in registry.run(call("calculate", "{broken"), CONTEXT)


def test_a_tool_failure_is_reported_not_raised(registry: ToolRegistry) -> None:
    result = registry.run(call("calculate", '{"expression": "1/0"}'), CONTEXT)

    assert "calculate failed" in result
    assert "zero" in result


def test_arguments_the_tool_cannot_use_are_reported(registry: ToolRegistry) -> None:
    """Calculator takes **kwargs, so a stray key reaches its own validation
    and produces a clearer message than a TypeError would."""
    result = registry.run(call("calculate", '{"nope": 1}'), CONTEXT)

    assert "calculate failed" in result
    assert "expression" in result


class BrokenTool:
    """A tool whose own code raises TypeError, which must not reach the user."""

    @property
    def name(self) -> str:
        return "broken"

    @property
    def description(self) -> str:
        return "always raises TypeError internally"

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def run(self, context: ToolContext, **kwargs: Any) -> str:
        return "x" + 1  # type: ignore[operator]


def test_a_type_error_inside_a_tool_is_contained() -> None:
    """The protocol takes **kwargs because the model sends arbitrary JSON, so
    a signature mismatch cannot happen -- but a TypeError raised *inside* a
    tool still must not become a 500."""
    registry = ToolRegistry([BrokenTool()])

    assert "wrong arguments" in registry.run(call("broken", "{}"), CONTEXT)


def test_the_registry_never_raises(registry: ToolRegistry) -> None:
    """A tool that cannot divide by zero is not a reason to fail the request."""
    for arguments in ("{}", "[]", "null", '{"expression": null}', "{{{"):
        assert isinstance(registry.run(call("calculate", arguments), CONTEXT), str)


def test_an_empty_registry_offers_nothing() -> None:
    assert ToolRegistry().catalogue() == []
