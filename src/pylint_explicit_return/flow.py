"""Track control flow through the statement suites in one function.

Each suite yields a bitset of possible exits. FALLTHROUGH advances to the
next statement in the enclosing suite. RETURN and RAISE can leave the
function, while loops consume BREAK and CONTINUE. A suite with no possible
exits can run indefinitely.
"""

from collections.abc import Sequence
from enum import IntFlag, auto

from astroid import nodes


class Exit(IntFlag):
    """Possible control transfers from a statement or suite."""

    NONE = 0
    FALLTHROUGH = auto()
    RETURN = auto()
    RAISE = auto()
    BREAK = auto()
    CONTINUE = auto()


def can_fall_through(body: Sequence[nodes.NodeNG]) -> bool:
    """Return whether execution can reach the end of a function body."""
    return bool(_suite_exits(body) & Exit.FALLTHROUGH)


def _suite_exits(body: Sequence[nodes.NodeNG]) -> Exit:
    """Advance fallthrough paths and retain transfers from earlier statements."""
    exits = Exit.FALLTHROUGH
    for statement in body:
        if not exits & Exit.FALLTHROUGH:
            break
        exits = (exits & ~Exit.FALLTHROUGH) | _statement_exits(statement)
    return exits


def _evaluation_exits(expression: nodes.NodeNG | None) -> Exit:
    """Return the possible exceptional exits from expression evaluation."""
    match expression:
        case None | nodes.Const():
            return Exit.NONE
        case nodes.List(elts=items) | nodes.Tuple(elts=items):
            return Exit.RAISE if any(_evaluation_exits(item) for item in items) else Exit.NONE
        case _:
            return Exit.RAISE


def _truth_value(test: nodes.NodeNG) -> bool | None:
    """Evaluate a literal test and leave runtime truth values unknown."""
    if isinstance(test, nodes.Const):
        return bool(test.value)
    return None


def _if_exits(statement: nodes.If) -> Exit:
    """Combine exits from the arms that the condition can select."""
    truth = _truth_value(statement.test)
    exits = _evaluation_exits(statement.test)
    if truth is not False:
        exits |= _suite_exits(statement.body)
    if truth is not True:
        exits |= _suite_exits(statement.orelse)
    return exits


def _literal_iterable_size(loop: nodes.For) -> int | None:
    """Get the size of a literal synchronous iterable without unpacking."""
    if isinstance(loop, nodes.AsyncFor):
        return None
    match loop.iter:
        case nodes.List(elts=items) | nodes.Tuple(elts=items):
            if all(not isinstance(item, nodes.Starred) for item in items):
                return len(items)
        case nodes.Const(value=str() | bytes() as value):
            return len(value)
    return None


def _loop_exits(loop: nodes.For | nodes.While) -> Exit:
    """Consume this loop's break and continue and handle its else suite."""
    if isinstance(loop, nodes.While):
        truth = _truth_value(loop.test)
        body = Exit.NONE if truth is False else _suite_exits(loop.body)
        can_exhaust = truth is not True
        exits = _evaluation_exits(loop.test)
    else:
        size = _literal_iterable_size(loop)
        body = Exit.NONE if size == 0 else _suite_exits(loop.body)
        # A nonempty literal reaches its else only if the body can advance.
        can_exhaust = not size or bool(body & (Exit.FALLTHROUGH | Exit.CONTINUE))
        exits = Exit.RAISE

    # A break reaches the next statement directly. Natural exhaustion
    # reaches the same statement only after the else suite completes.
    exits |= body & (Exit.RETURN | Exit.RAISE)
    if body & Exit.BREAK:
        exits |= Exit.FALLTHROUGH
    if can_exhaust:
        exits |= _suite_exits(loop.orelse)
    return exits


def _try_exits(statement: nodes.Try | nodes.TryStar) -> Exit:
    """Analyze handlers and else, then apply finally to every pending exit."""
    body = _suite_exits(statement.body)
    exits = body & ~Exit.FALLTHROUGH
    if body & Exit.RAISE:
        # A leading bare handler catches every body exception. A typed
        # handler's selector can itself raise before a later bare handler
        # has a chance to match.
        if statement.handlers and statement.handlers[0].type is None:
            exits &= ~Exit.RAISE
        for handler in statement.handlers:
            exits |= _suite_exits(handler.body)

    if body & Exit.FALLTHROUGH:
        exits |= _suite_exits(statement.orelse)

    if exits and statement.finalbody:
        final = _suite_exits(statement.finalbody)
        # Each abrupt exit in finally overrides the exit already in flight.
        exits = (exits if final & Exit.FALLTHROUGH else Exit.NONE) | (final & ~Exit.FALLTHROUGH)
    return exits


def _with_exits(statement: nodes.With) -> Exit:
    """Allow managers to raise during setup or cleanup and suppress exceptions."""
    exits = _suite_exits(statement.body)
    # Context managers can suppress exceptions from the body, an assignment to
    # a complex target, or entry/exit of a manager nested inside them.
    if exits & Exit.RAISE or len(statement.items) > 1:
        exits |= Exit.FALLTHROUGH
    if any(
        target is not None and not isinstance(target, nodes.AssignName)
        for _, target in statement.items
    ):
        exits |= Exit.FALLTHROUGH
    return exits | Exit.RAISE


def _pattern_exits(pattern: nodes.NodeNG) -> Exit:
    """Track possible mismatch (fallthrough) and exceptions during matching."""
    match pattern:
        case nodes.MatchAs(pattern=subpattern):
            return Exit.NONE if subpattern is None else _pattern_exits(subpattern)
        case nodes.MatchOr(patterns=alternatives):
            exits = Exit.FALLTHROUGH
            for alternative in alternatives:
                exits = (exits & ~Exit.FALLTHROUGH) | _pattern_exits(alternative)
                if not exits & Exit.FALLTHROUGH:
                    break
            return exits
        case _:
            return Exit.FALLTHROUGH | Exit.RAISE


def _match_exits(statement: nodes.Match) -> Exit:
    """Combine case exits and retain a path for a potentially unmatched value."""
    exits = _evaluation_exits(statement.subject)
    for case in statement.cases:
        pattern = _pattern_exits(case.pattern)
        exits |= pattern & Exit.RAISE
        truth = True if case.guard is None else _truth_value(case.guard)
        exits |= _evaluation_exits(case.guard)
        if truth is not False:
            exits |= _suite_exits(case.body)
        if not pattern & Exit.FALLTHROUGH and truth is True:
            return exits
    return exits | Exit.FALLTHROUGH


def _statement_exits(statement: nodes.NodeNG) -> Exit:
    """Compute transfers for one statement without visiting nested definitions."""
    # pylint: disable=too-many-return-statements
    match statement:
        case nodes.Return(value=value):
            return Exit.RETURN | _evaluation_exits(value)
        case nodes.Raise():
            return Exit.RAISE
        case nodes.Break():
            return Exit.BREAK
        case nodes.Continue():
            return Exit.CONTINUE
        case nodes.If():
            return _if_exits(statement)
        case nodes.For() | nodes.While():
            return _loop_exits(statement)
        case nodes.Try() | nodes.TryStar():
            return _try_exits(statement)
        case nodes.With():
            return _with_exits(statement)
        case nodes.Match():
            return _match_exits(statement)
        case nodes.Expr(value=value):
            return Exit.FALLTHROUGH | _evaluation_exits(value)
        case nodes.Pass() | nodes.Global() | nodes.Nonlocal():
            return Exit.FALLTHROUGH
        case _:
            # An opaque statement can raise or advance. This includes nested
            # definitions, whose bodies are analyzed independently.
            return Exit.FALLTHROUGH | Exit.RAISE
