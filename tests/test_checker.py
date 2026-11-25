"""Exercise the checker's diagnostics through Pylint."""

import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
from textwrap import dedent

import pytest
from pylint.lint import Run
from pylint.reporters import CollectingReporter

_PLUGIN = "pylint_explicit_return"
_MESSAGE = "missing-explicit-return"


def _check_source(tmp_path: Path, source: str, suffix: str = ".py") -> None:
    source = dedent(source).lstrip()
    target = tmp_path / f"example{suffix}"
    target.write_text(source, encoding="utf-8")
    config = tmp_path / "pylintrc"
    config.write_text("[MAIN]\n", encoding="utf-8")
    reporter = CollectingReporter()
    Run(
        [
            f"--rcfile={config}",
            f"--load-plugins={_PLUGIN}",
            "--disable=all",
            f"--enable={_MESSAGE}",
            str(target),
        ],
        reporter=reporter,
        exit=False,
    )
    expected_lines = [
        number
        for number, line in enumerate(source.splitlines(), start=1)
        if line.endswith("# missing")
    ]
    assert sorted((message.symbol, message.line) for message in reporter.messages) == [
        (_MESSAGE, line) for line in expected_lines
    ]
    return


def test_function_scopes(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        def test_example() -> None:  # missing
            assert True

        def empty():  # missing
            "Documentation only."

        def outer():  # missing
            def inner():
                return 1

        def another_outer():
            def another_inner():  # missing
                pass
            return

        def make_callback(flag):
            def callback():  # missing
                if flag:
                    return 1
            return callback

        class Example:
            def __init__(self) -> None:  # missing
                self.value = 1

            def method(self) -> None:
                return

        expression = lambda: None
        """,
    )
    return


def test_return_and_raise_paths(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        from typing import NoReturn

        def one_branch(condition):  # missing
            if condition:
                return

        def both_branches(condition):
            if condition:
                return 1
            else:
                raise ValueError("bad input")

        def partial_elif(value):  # missing
            if value == 1:
                return 1
            elif value == 2:
                return 2

        def complete_elif(value):
            if value == 1:
                return 1
            elif value == 2:
                return 2
            else:
                raise ValueError(value)

        def early_return(condition):
            if condition:
                return 1
            return

        def constant_branch():
            if True:
                return

        def dead_return():  # missing
            if False:
                return

        def unannotated_raise():
            raise ValueError

        def annotated_raise() -> NoReturn:
            raise ValueError

        def annotated_fallthrough() -> "NoReturn":  # missing
            pass
        """,
    )
    return


def test_loops(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        def possibly_empty(values):  # missing
            for value in values:
                return value

        def literal_sequence():
            for value in (1, 2):
                return value

        def empty_literal():  # missing
            for value in ():
                return value

        def while_false():  # missing
            while False:
                return

        def break_from_infinite_loop(flag):  # missing
            while True:
                if flag:
                    break
                return

        def inner_break_does_not_exit():
            while True:
                for _ in range(2):
                    break

        def loop_else_covers_exhaustion(items):
            for item in items:
                if item:
                    return item
                continue
            else:
                return None

        def loop_else_missed_on_break(items):  # missing
            for item in items:
                if item:
                    break
            else:
                return None

        def while_else_covers_exhaustion(items):
            while items:
                if items.pop():
                    return True
            else:
                return False

        def while_else_missed_on_break(items):  # missing
            while items:
                if items.pop():
                    break
            else:
                return False
        """,
    )
    return


def test_exception_paths(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        def catches_own_raise():  # missing
            try:
                raise ValueError
            except ValueError:
                pass

        def reraises():
            try:
                raise ValueError
            except ValueError:
                raise

        def return_expression_might_raise(f):  # missing
            try:
                return f()
            except Exception:
                pass

        def literal_return_never_enters_handler():
            try:
                return (1, None)
            except Exception:
                pass

        def else_exception_escapes():
            try:
                pass
            except ValueError:
                pass
            else:
                raise ValueError

        def else_only_reached_after_normal_completion(flag):  # missing
            try:
                if flag:
                    raise ValueError
            except ValueError:
                pass
            else:
                return

        def finally_preserves_return(action):
            try:
                return 1
            finally:
                action()

        def finally_overrides_fallthrough(action):
            try:
                action()
            finally:
                return

        def finally_raises_after_return():
            try:
                return 1
            finally:
                raise ValueError

        def finally_raises_after_fallthrough():
            try:
                pass
            finally:
                raise ValueError

        def finally_break_overrides_return():  # missing
            while True:
                try:
                    return
                finally:
                    break

        def finally_continue_overrides_return():
            while True:
                try:
                    return
                finally:
                    continue

        def exception_group():  # missing
            try:
                raise ExceptionGroup("bad", [ValueError()])
            except* ValueError:
                pass
        """,
    )
    return


def test_with_and_match(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        def with_return(manager):
            with manager:
                return 1

        def suppression_can_skip_return(manager, action):  # missing
            with manager:
                action()
                return

        def suppression_can_skip_body_assignment(manager):  # missing
            with manager as (first, second):
                return

        def match_complete(value):
            match value:
                case 1:
                    return 1
                case _:
                    raise ValueError

        def match_partial(value):  # missing
            match value:
                case 1:
                    return 1

        def match_guard_can_fail(value, guard):  # missing
            match value:
                case _ if guard:
                    return

        def match_or_with_capture(value):
            match value:
                case 1 | _:
                    return
        """,
    )
    return


def test_suspended_bodies(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        async def coroutine(f):  # missing
            await f()

        async def returning_coroutine(f):
            await f()
            return

        async def async_for_can_exhaust(values):  # missing
            async for value in values:
                return value

        def generator():  # missing
            yield 1

        def delegated_generator(other):  # missing
            yield from other

        def returning_generator():
            yield 1
            return 2

        async def async_generator():  # missing
            yield 1

        async def returning_async_generator(flag):
            yield 1
            if flag:
                raise ValueError
            return

        async def async_context_can_suppress(manager, f):  # missing
            async with manager:
                await f()
                return
        """,
    )
    return


def test_exceptions_at_suspension_points(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        from asyncio import CancelledError

        def swallow_throw():  # missing
            try:
                return (yield 1)
            except ValueError:
                pass

        def propagate_throw():
            try:
                return (yield 1)
            except ValueError:
                raise

        async def swallow_cancellation(operation):  # missing
            try:
                return await operation()
            except CancelledError:
                pass

        async def propagate_cancellation(operation):
            try:
                return await operation()
            except CancelledError:
                raise
        """,
    )
    return


def test_decorated_function_bodies(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        from contextlib import contextmanager
        from dataclasses import dataclass

        @contextmanager
        def manager():  # missing
            yield 1

        @dataclass
        class Record:
            value: int

            def __post_init__(self):  # missing
                self.value += 1

            @property
            def doubled(self):
                return self.value * 2

            @doubled.setter
            def doubled(self, value):  # missing
                self.value = value // 2
        """,
    )
    return


def test_declaration_and_executable_bodies(tmp_path: Path) -> None:
    _check_source(
        tmp_path,
        """
        from abc import ABC, abstractmethod as abstract
        from typing import overload as signature
        import typing as types
        import typing_extensions as extensions

        @signature
        def add(value: int) -> int: ...

        @extensions.overload
        def add(value: str) -> str: ...

        def add(value):  # missing
            pass

        class Contract(types.Protocol):
            def placeholder(self): ...

            def default(self):  # missing
                print("work")

        class Interface(ABC):
            @abstract
            def placeholder(self):
                "Documentation only."

            @abstract
            def executable(self):  # missing
                print("work")

        class Concrete:
            def placeholder(self):  # missing
                ...

        @abstract
        def standalone():  # missing
            ...

        def factory():
            @abstract
            def closure():  # missing
                pass
            return closure

        def overload(function):
            return function

        @overload
        def not_a_typing_overload():  # missing
            pass
        """,
    )
    return


def test_stub_file(tmp_path: Path) -> None:
    _check_source(tmp_path, "def signature() -> None: ...\n", suffix=".pyi")
    return


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("jobs", [1, 2])
def test_command_line_loads_and_suppresses_checker(
    tmp_path: Path, enabled: bool, jobs: int
) -> None:
    if jobs == 2:
        try:
            multiprocessing.Semaphore()
        except PermissionError:
            pytest.skip("This environment disallows multiprocessing semaphores")

    config = tmp_path / "pyproject.toml"
    config.write_text(
        dedent("""
            [tool.pylint.main]
            load-plugins = ["pylint_explicit_return"]

            [tool.pylint.messages_control]
            disable = ["all"]
            enable = ["missing-explicit-return", "inconsistent-return-statements"]
            """),
        encoding="utf-8",
    )
    first = tmp_path / "first.py"
    first.write_text(
        "# pylint: disable-next=missing-explicit-return\n"
        "def disabled_next():\n"
        "    pass\n\n"
        "def disabled_same_line():  # pylint: disable=missing-explicit-return\n"
        "    pass\n\n"
        "def missing():\n"
        "    pass\n",
        encoding="utf-8",
    )
    second = tmp_path / "second.py"
    second.write_text(
        "def bare():\n"
        "    return\n\n"
        "def mixed(flag):\n"
        "    if flag:\n"
        "        return 1\n"
        "    return\n",
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-m",
        "pylint",
        f"--rcfile={config}",
        f"--jobs={jobs}",
        "--output-format=json",
        str(first),
        str(second),
    ]
    if not enabled:
        command.append(f"--disable={_MESSAGE}")
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if (
        jobs == 2
        and sys.version_info >= (3, 15)
        and "AttributeError: 'code' object has no attribute 'co_lnotab'" in result.stderr
    ):
        pytest.xfail("Pylint's dill dependency cannot serialize workers on this Python version")
    assert result.returncode == (24 if enabled else 8), f"{result.stderr}\n{result.stdout}"
    messages = json.loads(result.stdout)
    actual = sorted((message["symbol"], message["obj"]) for message in messages)
    expected = [("inconsistent-return-statements", "mixed")]
    if enabled:
        expected.append((_MESSAGE, "missing"))
        assert [message["message-id"] for message in messages if message["symbol"] == _MESSAGE] == [
            "C8716"
        ]
    assert actual == expected, result.stderr
    return
