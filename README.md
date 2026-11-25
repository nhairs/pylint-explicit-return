# Pylint explicit return

`pylint-explicit-return` adds the Pylint diagnostic
`missing-explicit-return` (`C9701`). It reports functions that can reach
the end of their body implicitly. A bare return, a return expression, or an
escaping `raise` satisfies the rule on that path.

## Use the plugin

Install the package from this checkout into the environment that runs Pylint.
The plugin requires Python 3.11 or newer and Pylint 4.1.4 or newer in the 4.x
series.

```shell
python -m pip install .
```

Add the plugin and disable `useless-return` in your project's `pyproject.toml`.
If those lists already exist, append these entries.

```toml
[tool.pylint.main]
load-plugins = ["pylint_explicit_return"]

[tool.pylint.messages_control]
disable = ["useless-return"]
```

If parallel Pylint on Python 3.15 fails with a missing `co_lnotab` attribute
from `dill`, run Pylint with `-j 1`.

For example, the following function reports a diagnostic because
`print(value)` can finish and execution then reaches the end of the body.

```python
def save(value: str) -> None:
    if not value:
        raise ValueError("A value is required")
    print(value)
```

Add a bare `return` after `print(value)` to satisfy the rule. To suppress the
diagnostic for a single function, put
`# pylint: disable-next=missing-explicit-return` immediately above its
definition. Pylint's `inconsistent-return-statements` rule can remain enabled.
Use `return None` where a function's other branches return a value and you want
to satisfy both rules.

## How the checker handles paths

The checker analyzes every function body independently, including methods,
tests, nested functions, coroutines, and generators. A final `yield` or
`await` can resume and fall through. Use a bare `return` to end an async
generator explicitly. Return annotations such as `NoReturn` have no effect
on the diagnostic.

The checker skips `.pyi` files, typing overload signatures, and abstract or
protocol methods whose bodies contain only a docstring, `pass`, or an
ellipsis. It checks executable implementations and ordinary placeholder
functions.

The analysis is conservative about dynamic Python behavior. It treats
unknown iterables as potentially empty, considers exceptions from expressions
and possible handler matches, and assumes a context manager may suppress an
exception. It can therefore report fallthrough when a handler is unreachable
or a context manager never suppresses exceptions. Calls are assumed able to
return, and `match` exhaustiveness depends on an unguarded irrefutable
pattern or a subsequent exit.

## Develop

Use Python 3.11 or newer and uv. Run the checks with tox and tox-uv.

```shell
uvx --with tox-uv tox -e lint,py313
```

Run `uvx --with tox-uv tox` to use the full interpreter matrix, or run `uvx --with tox-uv tox -e format`
to format the code.

## Release

The release workflow uses nopt and runs when a version tag is pushed. Set the
version in `pyproject.toml` and update [the changelog](docs/changelog.md) before
tagging the matching commit. Configure the GitHub `pypi` environment and register
the repository, `release.yml` workflow, and environment as a PyPI Trusted
Publisher before the first release.

See the [nopt release instructions](https://github.com/nhairs/nicks-opinionated-python-package-publishing-tool#configure-a-project)
for tag, version, and changelog requirements.
