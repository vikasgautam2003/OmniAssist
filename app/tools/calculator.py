import ast
import operator
from typing import Any

from app.tools.base import ToolError

# Only these node types are evaluated. Anything else -- a name, a call, an
# attribute, a subscript -- is rejected before it runs.
_OPERATORS: dict[type[ast.AST], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

# 2 ** 10_000_000 is a valid expression that hangs the process and exhausts
# memory. Bounding the exponent is cheaper than timing the call out.
MAX_EXPONENT = 1000


def _evaluate(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int | float):
            raise ToolError("only numbers are allowed")
        return float(node.value)

    if isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ToolError("unsupported operator")
        return float(op(_evaluate(node.operand)))

    if isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if op is None:
            raise ToolError("unsupported operator")

        left, right = _evaluate(node.left), _evaluate(node.right)

        if isinstance(node.op, ast.Pow) and abs(right) > MAX_EXPONENT:
            raise ToolError(f"exponent larger than {MAX_EXPONENT} is not allowed")

        try:
            return float(op(left, right))
        except ZeroDivisionError as exc:
            raise ToolError("division by zero") from exc

    raise ToolError("that is not a plain arithmetic expression")


class Calculator:
    """Arithmetic, because language models are unreliable at it.

    Pure by design: it computes and returns, touching nothing. The first tools
    have no side effects because a tool catalogue turns prompt injection from
    something the model says into something it does.
    """

    @property
    def name(self) -> str:
        return "calculate"

    @property
    def description(self) -> str:
        return (
            "Evaluate an arithmetic expression and return the result. "
            "Use this for any calculation rather than working it out yourself. "
            "Supports + - * / // % ** and parentheses on plain numbers."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "An arithmetic expression, e.g. '(19 * 43) / 7'",
                }
            },
            "required": ["expression"],
        }

    def run(self, **kwargs: Any) -> str:
        expression = kwargs.get("expression")

        if not isinstance(expression, str) or not expression.strip():
            raise ToolError("an 'expression' string is required")

        try:
            # parse, never eval: eval on model output is remote code execution,
            # and the model's input can come from an uploaded document.
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ToolError(f"{expression!r} is not a valid expression") from exc

        result = _evaluate(tree)
        return str(int(result)) if result.is_integer() else str(result)
