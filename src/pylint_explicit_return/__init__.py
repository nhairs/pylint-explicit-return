"""Pylint checker that reports implicit fallthrough at the end of functions."""

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages
from pylint.lint import PyLinter

from .declarations import is_declaration
from .flow import can_fall_through


class ExplicitReturnChecker(BaseChecker):
    """Require an explicit return on each normally completing function path."""

    name = "explicit-return"
    msgs = {
        # 51–99 is Pylint's range for custom checker IDs.
        "C8716": (
            "Function %r can reach the end without an explicit return",
            "missing-explicit-return",
            "Used when a path falls through the end of a function body. "
            "An explicit return or an escaping raise terminates the path.",
        ),
    }

    @only_required_for_messages("missing-explicit-return")
    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        """Check a named function definition for fallthrough."""
        if not is_declaration(node) and can_fall_through(node.body):
            self.add_message("missing-explicit-return", node=node, args=(node.name,))
        return

    visit_asyncfunctiondef = visit_functiondef


def register(linter: PyLinter) -> None:
    """Register the checker with Pylint."""
    linter.register_checker(ExplicitReturnChecker(linter))
    return
