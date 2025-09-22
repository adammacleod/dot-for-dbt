# Contributing to dot

Thank you for your interest in contributing to dot! Your help is greatly appreciated. This guide will help you get started and understand the conventions and processes for contributing to the project.

## Code of Conduct

Please be respectful and considerate in all interactions. We welcome contributions from everyone.

## Code Structure

Core package import name is `dot` (distribution on PyPI is `dot-for-dbt`).

- `src/dot/cli.py` – Argument parsing, top‑level CLI entry (`app()`), dispatch to command construction.
- `src/dot/dot.py` – Core orchestration logic: environment resolution via `dot_environments.yml`, variable spec via `dot_vars.yml`, allowed arg filtering, isolated build handling, dbt command assembly.
- `src/dot/git.py` – Git repository discovery, commit/ref resolution, worktree creation for isolated builds.
- `src/dot/profiles.py` – Detection of active `profiles.yml` (via `dbt debug --config-dir`) and generation of isolated profiles with schema suffixing.
- `src/dot/__init__.py` – Dynamic `__version__` exposure via package metadata (no manual edits).
- `src/dot/__main__.py` – Enables `python -m dot` invocation (delegates to CLI).
- `tests/` – Test suite (currently minimal hash resolution test; expand with CLI/integration tests).
- `example_dbt_project/` – Sample dbt project used for manual / future automated integration testing.
- `adr/` – Architectural Decision Records (e.g. isolated builds rationale).
- `development_plans/` – Approved development plans and design exploration.
- `CHANGELOG.md` – Version history (Keep a Changelog format).
- `pyproject.toml` – Project metadata, build backend (hatchling), uv TestPyPI index, hatch file selection config.
- `README.md` – End‑user documentation (installation, usage, concepts) – intentionally excludes release procedure.
- `CONTRIBUTING.md` – Contributor workflow, release process, versioning guidance.

Design Key Points:
- Distribution name differs from import name (`dot-for-dbt` vs `dot`) for PyPI uniqueness.
- Isolated builds leverage git worktrees + rewritten profiles for schema isolation.
- Execution configuration bundles formerly called “context” are now “environment” (breaking rename with no backward compatibility).

## Getting Started

### Local Install for Development

Installs `dot` in your system from this directory. The -e option makes uv automatically update the installed app for any code changes in the repository.

```bash
uv tool install . -e
```

### Running Tests

After any code changes, always run:

```bash
uv run pytest -q
```

You can also do a manual smoke inside the example project (ensure a profile/warehouse is configured first):

```bash
cd example_dbt_project
dot build
```

## Contributing Guidelines

- Open an issue to discuss any major changes before submitting a pull request.
- Follow modern Python tooling and conventions (e.g., [uv](https://github.com/astral-sh/uv)).
- Keep the codebase clean and well-documented.
- Update the README.md and this file if your changes affect usage or development.
- Document major design decisions using an ADR (Architectural Decision Register). See the [adr/](adr/) directory for existing decisions, including [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md), which describes the isolated builds workflow.

### Startup Prompt Framework

A modular prompt system (see `src/dot/cli_prompts.py`) runs early in the CLI to enforce or suggest project hygiene tasks:

Current prompt tasks:
1. `gitignore` (mandatory unless disabled)
2. `vscode` (optional editor settings exclusion for `.dot`)

Configuration (`.dot/config.yml`):
```yaml
prompts:
  gitignore: enabled | disabled
  vscode: enabled | disabled
```
Missing keys default to `enabled`. Selecting `e` (never) at a prompt persists `disabled`. Global suppression for a single run: `--disable-prompts` (also auto-applied when non-interactive: `not sys.stdin.isatty()`).

Adding a new prompt task:
1. Define a detector returning `DetectorResult.COMPLIANT | NEEDS_ACTION | SKIP`.
2. Define an apply function that performs the change idempotently (no-op if already compliant).
3. Provide a `message_builder()` returning the prompt text.
4. Register a `PromptTask` in `cli_prompts.py` with:
   - `id`
   - `detector`
   - `apply`
   - `message_builder`
   - `config_disable_key` (e.g. `prompts.myfeature`)
   - `abort_on_no` (True if declining should abort)
5. Write tests covering: compliant, needs action + yes/no/never, disabled state, global disable, non-interactive.
6. Update README (if end-user visible) and CHANGELOG under Unreleased.
7. Avoid storing extra state; rely only on enabled/disabled plus filesystem detection.

Guidelines:
- Never write user files on parse failure (emit manual instructions instead).
- Keep apply operations atomic where possible.
- Log summary line: `Prompt summary: ...`.
- Prefer conservative merges (only add required keys).

## Deferred Builds (Commit-Based Deferral)

The defer feature allows a dbt command to treat previously built nodes as complete by pointing dbt to the artifacts (`manifest.json`, etc.) of a prior isolated build. Implementation constraints:

- Commit-based only: defer specs must include a git ref (`env@ref` or `@ref`).
- Workspace (mutable) deferral intentionally excluded to preserve reproducibility and CI parity.
- Baseline path: `.dot/build/<short_hash>/env/<env>/target`.
- Validation performed before spawning dbt: environment existence, git ref resolution, directory presence, `manifest.json` presence.
- Flags injected: `--defer --favor-state --state <path>` (allow‑list extended for build/run/test).

Testing requirements for changes touching deferral:
1. Negative specs (`env`, `env@`, `@`, multiple `@`) produce correct error text.
2. Missing baseline directory and missing manifest produce correct errors.
3. Successful injection includes all three flags and correct path (normalized separators on Windows).
4. Same (env, ref) for active and defer still works (idempotent injection).
5. Unknown environment / missing default environment error cases covered.

When adding new dbt subcommands that may benefit from deferral:
- Extend `DBT_COMMAND_ARGS` to include `--state`, `--favor-state`, and `--defer` as appropriate.
- Add integration test ensuring flags pass through.

## How to Get Help

If you have questions, open an issue or start a discussion in the repository.

We look forward to your contributions!

## License

By contributing, you agree that your contributions will be licensed under the MIT License. See the `LICENSE` file for details.

SPDX-License-Identifier: MIT

## Release & Publishing Process

This project is published to PyPI as `dot-for-dbt`. All release tasks use `uv` only (no twine). TestPyPI index configured in `pyproject.toml` (`[[tool.uv.index]]`).

### 1. Preconditions

- `CHANGELOG.md` updated (move Unreleased entries under new version).
- `README.md` updated if features / usage changed.
- Tests pass: `uv run pytest -q`.
- Clean working tree on `main`.

### 2. Select Version (Semantic Versioning)

Preview current version:
```bash
uv version
```

Bump automatically:
```bash
# choose one
uv version --bump patch
uv version --bump minor
uv version --bump major
```

Or set explicitly:
```bash
uv version 0.1.2
```

Dry run:
```bash
uv version --bump patch --dry-run
```

This edits `pyproject.toml`. Commit & tag:
```bash
git add pyproject.toml CHANGELOG.md uv.lock
git commit -m "Release vX.Y.Z"
git tag -a vX.Y.Z -m "vX.Y.Z"
```

### 3. Build Artifacts

Before building, remove old files from the `dist/` directory to avoid publishing outdated releases:

```powershell
Remove-Item dist\*
```

Use isolated resolution (disable sources) to ensure reproducibility:

```bash
uv build --no-sources
```
Outputs: `dist/*.whl` and `dist/*.tar.gz`.

Optional inspection:
```bash
tar -tzf dist/dot_for_dbt-X.Y.Z.tar.gz | head
```

### 4. Local Install Smoke Test

```bash
uv venv --seed .venv-release
.\.venv-release\Scripts\python -m pip install dist\dot_for_dbt-X.Y.Z-py3-none-any.whl
.\.venv-release\Scripts\python -c "import dot; print(dot.__version__)"
```

### 5. TestPyPI Publish (Optional but Recommended)

Set token (PowerShell):
```powershell
$env:UV_PUBLISH_TOKEN=$env:TEST_PYPI_TOKEN
uv publish --index testpypi
```
Or provide inline:
```bash
UV_PUBLISH_TOKEN=$TEST_PYPI_TOKEN uv publish --index testpypi
```

### 6. Validate From TestPyPI

Use separate clean environment to avoid local artifacts:
```bash
uv venv --seed .venv-testpypi
.\.venv-testpypi\Scripts\python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple dot-for-dbt
.\.venv-testpypi\Scripts\python -c "import dot; print(dot.__version__)"
```

### 7. Production Publish

Set production token:
```powershell
$env:UV_PUBLISH_TOKEN=$env:PYPI_TOKEN
uv publish
```
(Equivalent to `--token`.)

If using Trusted Publisher (CI), configure in PyPI project settings; then CI can run plain `uv publish`.

### 8. Post Release

```bash
git push && git push --tags
```
Verify: https://pypi.org/project/dot-for-dbt/
Optionally create GitHub Release referencing tag & changelog notes.

### 9. Hotfix Flow

1. Branch from latest tag.
2. Apply fix.
3. `uv version --bump patch`
4. Repeat build + publish steps (can skip TestPyPI if trivial & urgent).

### 10. Do Not Manually Edit __version__

`__version__` is resolved via metadata at runtime. Only change via `uv version`.

### 11. Common Issues

| Symptom | Cause | Action |
|---------|-------|--------|
| 403 on publish | Wrong / missing token | Ensure `UV_PUBLISH_TOKEN` set & scoped to project |
| Version exists | Immutable PyPI | Bump version (`uv version --bump patch`) |
| Missing files in sdist | Not included | Check hatch include list & rebuild |
| Local code imported instead of installed | Path precedence | Use `uv venv` + explicit install |
| TestPyPI install pulls prod deps only | Index precedence | Always use `--index-url testpypi --extra-index-url pypi` |

### 12. Security Recommendations

- Prefer per‑project PyPI tokens.
- Never commit tokens; use environment variables or CI secrets.
