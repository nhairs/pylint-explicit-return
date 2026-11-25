"""Smoke tests for the installed package."""

from importlib import import_module


def test_package_is_importable() -> None:
    """The distribution installs the public Python module."""
    assert import_module("pylint_explicit_return").__name__ == "pylint_explicit_return"
    return
