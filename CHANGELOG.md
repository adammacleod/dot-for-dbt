# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres (from now on) to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.1] - 2025-09-11

### Changed
- Logging output improvements

## [0.4.0] - 2025-09-08

### Added
- Configuration split introducing three-file model (see ADR 0002 & 0003):
  - `dot_vars.yml` for variable specifications (description, values, strict, required).
  - `dot_environments.yml` for project environment definitions and variable value assignments.
  - `dot_environments.user.yml` (uncommitted) for local developer overrides (takes precedence over project file).

### Changed
- Deep merge now limited to `environment.*.vars` mappings; other environment keys merge shallowly.
- User override file merges into project environments with per-variable overrides instead of wholesale replacement.

### Removed
- Support for root-level `vars` in environment configuration files (must reside in `dot_vars.yml`).

### Documentation
- Added ADR 0002 (Environments Configuration & Overrides) and ADR 0003 (Variable Specifications) describing the new architecture.
- README & CONTRIBUTING updated to reflect separation of specification vs assignment and user override precedence.

### Notes
- Undeclared variables assigned in environments are passed through without warning (intentional flexibility).

## [0.3.0] - 2025-09-07

### Changed
- Isolated build directory key now uses the git short hash (`git rev-parse --short <ref>`) instead of the full 40-character hash (mitigates Windows path length issues).
- Directory structure updated to `.dot/build/<short_hash>/worktree/`, `env/<environment>/` (`profiles.yml`, `target/`, `logs/`) plus a `commit` metadata file.
- On-disk directory renamed from `.dot/isolated_builds/` to `.dot/build/` (documentation updated; ADR & development plan filenames unchanged for historical continuity).
- BREAKING: Renamed vars.yml top-level key `context` to `environment` and CLI positional argument `<context>` to `<environment>` (no backward compatibility retained).

### Added
- `commit` file inside each isolated build directory containing the full 40-character commit hash for audit and reverse mapping.

### Removed
- `pygit2` dependency (all git operations now via core git CLI).
- Custom/legacy collision handling logic (rely solely on git’s abbreviation expansion).

### Documentation
- ADR 0001 and Development Plan 0001 rewritten to reflect short-hash strategy, path length rationale, commit metadata file, and git CLI usage.
- README / CONTRIBUTING aligned with simplified isolated build design (short hash, commit file, no pygit2).

### Fixed
- Windows subprocess test failure by replacing non-executable `["echo","mocked"]` mock with a portable Python command in `tests/test_cli_gitignore.py`.

### Internal
- Tests updated for short-hash directory scheme and mandatory commit metadata file.
- Simplified git/ref resolution code paths and removed obsolete logic.

## [0.2.0] - 2025-09-07

### Added
- Integrated rich-based logging for improved CLI output and diagnostics.
- Enforced .gitignore checks to ensure `.dot/` directory is ignored before running commands.

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
