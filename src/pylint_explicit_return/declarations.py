"""Recognize declaration-only bodies through their import bindings and syntax."""

from astroid import nodes
from pylint.checkers.utils import is_in_stub_file, safe_infer

_OVERLOADS = {"typing.overload", "typing_extensions.overload"}
_PROTOCOLS = {"typing.Protocol", "typing_extensions.Protocol"}
_ABSTRACT_DECORATORS = {
    "abc.abstractmethod",
    "abc.abstractclassmethod",
    "abc.abstractstaticmethod",
    "abc.abstractproperty",
}


def _binding_name(binding: nodes.NodeNG, local_name: str) -> str | None:
    """Recover the original name of an import or an inferable alias."""
    if isinstance(binding, nodes.Import):
        for imported, alias in binding.names:
            head = imported.split(".", 1)[0]
            if local_name == (alias or head):
                return imported if alias else head
    elif isinstance(binding, nodes.ImportFrom) and not binding.level:
        for imported, alias in binding.names:
            if local_name == (alias or imported):
                return f"{binding.modname}.{imported}"
    elif isinstance(binding, nodes.AssignName):
        inferred = safe_infer(binding)
        if isinstance(inferred, (nodes.Module, nodes.ClassDef, nodes.FunctionDef)):
            return inferred.qname()
    return None


def _reference_parts(expression: nodes.NodeNG) -> tuple[str, ...]:
    """Split a dotted reference into its looked-up name and attributes."""
    match expression:
        case nodes.Name(name=name):
            return (name,)
        case nodes.Attribute(expr=base, attrname=attr):
            parts = _reference_parts(base)
            return (*parts, attr) if parts else ()
        case _:
            return ()


def _qualified_name(
    expression: nodes.NodeNG,
    definition: nodes.FunctionDef | nodes.ClassDef,
) -> str | None:
    """Resolve a decorator or base only when its visible bindings agree."""
    parts = _reference_parts(expression)
    if not parts:
        return None
    root, *attributes = parts
    # Decorators and bases are evaluated in the scope containing the
    # definition. Bindings inside a method or class body are out of scope.
    _, bindings = definition.parent.scope().scope_lookup(definition, root)
    names = {_binding_name(binding, root) for binding in bindings}
    if len(names) == 1:
        name = names.pop()
        if name is not None:
            return ".".join((name, *attributes))
    return None


def _is_protocol(cls: nodes.NodeNG) -> bool:
    """Recognize a class that declares typing.Protocol as a base."""
    if not isinstance(cls, nodes.ClassDef):
        return False
    for base in cls.bases:
        expression = base.value if isinstance(base, nodes.Subscript) else base
        if _qualified_name(expression, cls) in _PROTOCOLS:
            return True
    return False


def is_declaration(function: nodes.FunctionDef) -> bool:
    """Identify stubs, overloads, and placeholder-only interface methods."""
    if is_in_stub_file(function):
        return True

    decorators = function.decorators.nodes if function.decorators else []
    names = {_qualified_name(decorator, function) for decorator in decorators}
    if names & _OVERLOADS:
        return True

    # Astroid stores the docstring separately, so a docstring-only body
    # appears empty. Interface placeholders may also use pass or ellipsis.
    for statement in function.body:
        if isinstance(statement, nodes.Pass):
            continue
        if isinstance(statement, nodes.Expr) and isinstance(statement.value, nodes.Const):
            if statement.value.value is Ellipsis:
                continue
        return False

    return bool(names & _ABSTRACT_DECORATORS) or _is_protocol(function.parent.scope())
