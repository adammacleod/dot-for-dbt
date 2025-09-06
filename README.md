# The Data Orchestration Tool for dbt (dot-for-dbt)

`dot` is a lightweight companion CLI for dbt that lets you run any dbt command for an optional named context and an exact git commit/ref using the shorthand `<context?>@<ref>`. Adding `@<ref>` builds that historical version into a schema automatically suffixed with the commit’s short hash (e.g. `analytics_a1b2c3d4`) so your current schemas stay untouched. This enables reproducible historical builds, safe experimentation, side‑by‑side diffing, and confident migration or release validation.

## Installation

Requires Python >= 3.12 (resolved automatically by `uv`).

Using `uv` (recommended persistent install):
```bash
uv tool install dot-for-dbt
dot --help
```

Upgrade:
```bash
uv tool upgrade dot-for-dbt
```

Ephemeral run (no global install):
```bash
uvx dot-for-dbt --help
```

Pin version:
```bash
uv tool install dot-for-dbt==0.1.1
uvx dot-for-dbt==0.1.1 --help
```

Via `pip` (alternative):
```bash
pip install dot-for-dbt
```

Uninstall:
```bash
uv tool uninstall dot-for-dbt
```

## Quick Example

```bash
# Build current project using default context
dot build

# Build historical commit (isolated schema)
dot build @abc1234

# Build specific context at a ref
dot run dev@feature/my-branch
```

## CLI Usage

Basic usage:

```sh
dot <dbt_command> <context>
```

- `<dbt_command>` is any supported dbt command (e.g., build, run, test).
- `<context>` (Optional) is the environment/context which you want to target as defined in your `vars.yml`. If you do not specify a context, the default context from `vars.yml` will be used.

To build or run against a specific git commit in an isolated schema, append `@<gitref or commit>` to the context:

```sh
dot <dbt_command> <context>@<gitref or commit>
```

You can also build into the default context at a certain commit:

```sh
dot <dbt_command> @<gitref or commit>
```

This will check out the specified commit in a git worktree, generate a dedicated `profiles.yml`, and build into `yourschema_<short git hash>`. This enables reproducible, isolated builds for any point in your repository history.

## vars.yml Behavior

- `vars.yml` is optional. If it does not exist in your working directory, dot will proceed with default settings and no context-based variables.
- If `vars.yml` exists but is malformed (invalid YAML), dot will print an error and exit.
- If you specify a context that does not exist in `vars.yml`, dot will print an error and exit.
- If no context is specified and no default is set in `vars.yml`, dot will proceed with default settings.

## Isolated Builds

Isolated builds let you execute a dbt command against the exact contents of any git commit (or ref) in a clean, temporary worktree while writing all database objects into a schema that is namespaced by the commit hash. This provides:

- Reproducibility (build exactly what existed at that commit)
- Confidence to roll forward/back by inspecting isolated artifacts

Future features are planned to make more extensive use of isolated builds

### Quick Start

To build using the default context specified in `vars.yml` at a particular historical git reference, simply omit the context and use `@<ref>`:

```sh
dot build @abc1234
```

Build an explicit context against a ref:
```sh
dot run dev@feature/my-branch
dot test prod@v1.2.0
```

Build using a short or symbolic ref (branch, tag, HEAD~N, etc.):
```sh
dot run dev@HEAD~1
dot build prod@main
```

### Syntax Summary

```
<context?>@<gitref>
```
- `context` (optional) — name defined under `context` in `vars.yml`
- `gitref` (optional) — branch, tag, full/short hash, reflog expression, etc.
- If `@<gitref>` is supplied with no leading context, the default context is used.
- If no `@` suffix is provided, this is a normal (non‑isolated) build against the current state of your project.

### What Happens Internally

1. Resolve the supplied `<gitref>` to a full commit hash.

2. Construct: `.dot/isolated_builds/<commit_hash>/`

3. Create (or reuse if it already exists) a clean git worktree at:
   ```
   .dot/isolated_builds/<commit_hash>/worktree/
   ```

4. Locate the dbt project inside that worktree matching your original working project path.

5. Detect the active `profiles.yml` location by invoking `dbt debug --config-dir`.

6. Read the selected profile + target (your context name).

7. Write an isolated `profiles.yml` to:
   ```
   .dot/isolated_builds/<commit_hash>/<context>/profiles.yml
   ```
   with the target schema updated to <schema>_<commit_hash>.

8. Set dbt CLI args so that:
   - `--project-dir` points at the isolated worktree project
   - `--profiles-dir` points at `.dot/isolated_builds/<commit_hash>/<context>`
   - `--target-path` is `.dot/isolated_builds/<commit_hash>/<context>/target`
   - `--log-path` is `.dot/isolated_builds/<commit_hash>/<context>/logs`

9. Execute your dbt command.

### Schema Naming

The target schema becomes:

```
<original_schema>_<short_hash>
```

Where `<short_hash>` is the first 8 characters of the full commit hash. For example, if your original target schema is `analytics` and the commit is `6b777b8c94771a74...`, the isolated schema is:

```
analytics_6b777b8c
```

### Directory Layout

Example layout for an isolated build:

```
.dot/
  isolated_builds/
    <full_commit_hash>/
      worktree/             # Clean checkout at that commit
      dev/                  # One folder per context used with this commit
        profiles.yml        # Auto-generated, schema rewritten with _<short_hash>
        target/             # dbt artifacts (manifest, run results, etc.)
        logs/               # dbt logs for this isolated run
      prod/
        profiles.yml
        target/
        logs/
```

If you build multiple contexts (`dev`, `prod`) for the same commit, each gets its own context subdirectory.

### Examples

Diff models between current development and a feature branch:
```sh
dot build dev
dot build dev@feature/new-metric
# Compare artifacts or query both schemas: analytics vs analytics_<shot_hash>
```

Test a migration before merging:
```sh
dot run prod@migration/rename-columns
dot test prod@migration/rename-columns
```

Roll forward validation (red/green):
```sh
dot build prod@current_prod_tag
dot build prod@next_release_candidate
# Validate row counts, constraints, performance before switching consumers
```

Historical investigation:
```sh
dot run dev@2024-12-01-tag
```

### profiles.yml Detection & Rewriting

`dot` invokes `dbt debug --config-dir` (wrapped through its own command builder) to locate the effective `profiles.yml`. It then:
- Loads the user’s configured profile
- Extracts the target matching the active context
- Updates only the `schema` field (preserving credentials, threads, etc.)
- Writes a minimal isolated `profiles.yml` containing just that profile + target

### Passing Additional dbt Args

Anything after `--` is passed through untouched:
```sh
dot run dev@main -- --select my_model+
```

### Cleanup

Currently there is no automatic cleanup. To reclaim space:

- Drop old schemas manually from your warehouse
- Remove stale directories under `.dot/isolated_builds/`

Automatic management of old build artifacts and schemas is planned for a future release. Please let me know if this would be important to you!

### Troubleshooting

| Symptom | Cause | Action |
|---------|-------|--------|
| Error: Profile not found | Active context or profile missing | Verify `profiles.yml` and context name |
| Commit not found | Bad ref | Run `git show <ref>` to validate |
| Schema clutter | Many builds kept | Periodically prune `.dot/isolated_builds` and drop old schemas |
| Wrong default context | `context.default` unset or unexpected | Set `default` under `context` in `vars.yml` |

### Reference

For architectural rationale see: [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md).

## Architectural Decision Records

Architectural decisions are documented in the [adr/](adr/) directory.

- [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for released versions.

## License

This project is licensed under the MIT License. See the `LICENSE` file for full details.

SPDX-License-Identifier: MIT
