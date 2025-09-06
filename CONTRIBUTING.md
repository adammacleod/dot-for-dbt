# Contributing to dot

Thank you for your interest in contributing to dot! Your help is greatly appreciated. This guide will help you get started and understand the conventions and processes for contributing to the project.

## Code of Conduct

Please be respectful and considerate in all interactions. We welcome contributions from everyone.

## Code Structure

- CLI handling is in `src/dot/cli.py`.
- All reusable logic (config loading, context resolution, command construction) is in `src/dot/dot.py`.

## Getting Started

### Local Install for Development

Installs `dc` in your system from this directory. The -e option makes uv automatically update the installed app for any code changes in the repository.

```bash
uv tool install . -e
```

### Running Tests

After any code changes, always run:

```bash
cd example_dbt_project
dot build prod
```

## Contributing Guidelines

- Open an issue to discuss any major changes before submitting a pull request.
- Follow modern Python tooling and conventions (e.g., [uv](https://github.com/astral-sh/uv)).
- Keep the codebase clean and well-documented.
- Update the README.md and this file if your changes affect usage or development.
- Document major design decisions using an ADR (Architectural Decision Register). See the [adr/](adr/) directory for existing decisions, including [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md), which describes the isolated builds workflow.

## How to Get Help

If you have questions, open an issue or start a discussion in the repository.

We look forward to your contributions!

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See the `LICENSE` file for details.

SPDX-License-Identifier: MIT

## Release & Publishing Process

This project is published to PyPI as `dot-for-dbt`.

### 1. Preconditions

- Ensure `CHANGELOG` (if added later) and `README.md` reflect new features.
- All tests pass locally.
- Working tree clean and on `main` (or the designated release branch).

### 2. Bump Version

Edit the version in `pyproject.toml`:

```
[project]
version = "X.Y.Z"
```

Follow semantic versioning:
- Patch: bug fixes
- Minor: backwards‑compatible features
- Major: breaking changes

Commit the version bump:

```
git add pyproject.toml
git commit -m "release: vX.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z"
```

### 3. Build Artifacts

Use uv (hatchling backend):

```
uv build
```

Artifacts appear in `dist/` (wheel + sdist).

### 4. Verify Artifacts

```
uv run twine check dist/*
```

(Optional) Inspect sdist contents:

```
tar -tzf dist/dot-for-dbt-X.Y.Z.tar.gz
```

### 5. Test Upload (Recommended)

Create a TestPyPI token (scoped to project name) and set:

```
set TEST_PYPI_TOKEN=...   (Windows cmd)
# or
$env:TEST_PYPI_TOKEN="..."  (PowerShell)
```

Upload:

```
uv run twine upload -r testpypi dist/*
```

Install from TestPyPI into a clean virtual env:

```
uv venv --seed .venv-test
.venv-test\Scripts\python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple dot-for-dbt
python -c "import dot; print(dot.__version__)"
```

Run a quick smoke test in a sample dbt project if possible.

### 6. Production Upload

Set real PyPI token:

```
set PYPI_TOKEN=...
```

Upload:

```
uv run twine upload dist/*
```

(You can also use `twine upload -r pypi dist/*` explicitly.)

### 7. Post Release

- Push commits and tags:

```
git push && git push --tags
```

- Verify project page: https://pypi.org/project/dot-for-dbt/
- Optionally create a GitHub Release referencing the tag.

### 8. Hotfix Flow

For a hotfix:
1. Branch from the release tag (or `main` if fast-forward).
2. Apply fix, bump patch version, repeat steps above.

### 9. Do Not Manually Edit __version__

Runtime version is resolved dynamically via importlib.metadata. Only bump `pyproject.toml`.

### 10. Common Issues

| Symptom | Action |
|---------|--------|
| 403 on upload | Check token scope / project name collision |
| Version already exists | Increment version (PyPI is immutable) |
| Missing files in sdist | Ensure they are not excluded by .gitignore (hatchling respects VCS) |
