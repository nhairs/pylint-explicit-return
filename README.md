# Pylint explicit return

`pylint-explicit-return` is a Pylint plugin in development. It will flag
functions that can finish without an explicit `return`, with an exemption
for functions annotated `NoReturn`. The package currently contains the
development and release setup.

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
