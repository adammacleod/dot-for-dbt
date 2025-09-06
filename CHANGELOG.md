# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres (from now on) to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Adopted uv-native release workflow (replacing `twine upload` with `uv publish`).
- Added TestPyPI index configuration to `pyproject.toml` (`[[tool.uv.index]]` with publish-url).
- Removed `twine` from dev optional dependencies.

### Documentation
- Updated `CONTRIBUTING.md` with uv-only release process (version bump via `uv version`, `uv build --no-sources`, `uv publish`, TestPyPI + production steps).
- Updated `README.md` Packaging & Release Summary to reflect uv workflow.
- Added release token environment variable guidance (`UV_PUBLISH_TOKEN`).

### Notes
- Future releases should use `uv version --bump` for semver changes.
- Trusted Publisher (PyPI) can be configured later for CI automation.

## [0.1.1] - 2025-09-05
First public PyPI release of `dot-for-dbt` (renamed from internal `dot`).

### Added
- Dynamic runtime version resolution via `importlib.metadata` (`src/dot/__init__.py`).
- Hatch build configuration (`[tool.hatch.build.targets.wheel]` and sdist include list).
- Project metadata: authors, keywords, URLs, optional dev dependencies.
- Release & publishing process documentation in `CONTRIBUTING.md`.
- Installation, packaging & release summary, and quick examples in `README.md`.
- This `CHANGELOG.md`.

### Changed
- Distribution/package name to `dot-for-dbt` (wheel/SDist now `dot_for_dbt-*`).
- Updated test to use `get_commit_hash_from_gitref` (removed reference to old `resolve_git_ref` name).
- Added explicit package selection for hatch to resolve build failure.

### Fixed
- Build failure: “Unable to determine which files to ship” resolved by specifying `packages = ["src/dot"]`.

### Publishing Actions
- Built artifacts with `uv build`.
- Verified with `twine check`.
- Uploaded to TestPyPI and validated install in clean venv.
- Published to PyPI: https://pypi.org/project/dot-for-dbt/0.1.1/

### Notes
- Runtime version comes from metadata; do not hardcode `__version__`.
- Future: add richer test coverage (CLI invocation, isolated build scenarios) and automated release workflow.
