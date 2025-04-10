import ast
import operator
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime

from unpage.plugins.base import Plugin
from unpage.plugins.mixins.mcp import McpServerMixin, tool


class CorePlugin(Plugin, McpServerMixin):
    @tool()
    def current_datetime(self) -> AwareDatetime:
        """Return the current date and time in UTC."""
        return datetime.now(UTC)

    @tool()
    def convert_to_timezone(self, datetime: AwareDatetime, timezone: str) -> AwareDatetime:
        """Convert a datetime to a specific timezone."""
        return datetime.astimezone(ZoneInfo(timezone))

    @tool()
    def calculate(self, expression: str) -> str:
        """Evaluate a mathematical expression."""
        allowed_operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.FloorDiv: operator.floordiv,
            ast.Mod: operator.mod,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

        def eval_expr(node: ast.AST) -> float:
            if isinstance(node, ast.Constant):
                if isinstance(node.value, str | int | float):
                    return float(node.value)
                raise ValueError(f"Unsupported constant type: {type(node.value)}")
            elif isinstance(node, ast.BinOp):
                left = eval_expr(node.left)
                right = eval_expr(node.right)
                op_type = type(node.op)
                if op_type in allowed_operators:
                    return allowed_operators[op_type](left, right)
            elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
                return eval_expr(ast.UnaryOp(op=ast.USub(), operand=node.operand))
            raise ValueError(f"Unsupported operation: {ast.dump(node)}")

        return str(eval_expr(ast.parse(expression, mode="eval").body))
