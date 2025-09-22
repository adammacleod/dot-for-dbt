# The Data Orchestration Tool for dbt (dot-for-dbt)

`dot` is a lightweight companion CLI for dbt that lets you run any dbt command for an optional named environment and an exact git commit/ref using the shorthand `<environment?>@<ref>`. Adding `@<ref>` builds that historical version into a schema automatically suffixed with the commit’s short hash (e.g. `analytics_a1b2c3d4`) so your current schemas stay untouched. This enables reproducible historical builds, safe experimentation, side‑by‑side diffing, and confident migration or release validation.

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
# Build current project using default environment
dot build

# Build historical commit (isolated schema)
dot build @abc1234

# Build specific environment at a ref
dot run dev@feature/my-branch
```

## CLI Usage

Basic usage:

```sh
dot <dbt_command> <environment> [--dry-run] [--disable-prompts]
```

- `<dbt_command>` is any supported dbt command (e.g., build, run, test).
- `<environment>` (Optional) is the environment which you want to target as defined in your `dot_environments.yml` under the top-level `environment:` key. If you do not specify an environment, the default environment from `dot_environments.yml` will be used.

To build or run against a specific git commit in an isolated schema, append `@<gitref or commit>` to the environment:

```sh
dot <dbt_command> <environment>@<gitref or commit>
```

You can also build into the default environment at a certain commit:

```sh
dot <dbt_command> @<gitref or commit>
```

This will check out the specified commit in a git worktree, generate a dedicated `profiles.yml`, and build into `yourschema_<short git hash>`. This enables reproducible, isolated builds for any point in your repository history.

### Passing Additional dbt Args to the CLI

Anything after `--` is passed through untouched:
```sh
dot run dev@main -- --select my_model+
```

## Startup Prompts

`dot` will prompt you to complete these two tasks unless you already have them configured, have chosen to ignore them, or you run with `--disable-prompts`. These two changes help prevent serious problems, and are strongly encouraged.

You can also suppress all prompts with `--disable-prompts`, eg: `dot build --disable-prompts`. This is strongly discouraged, but could be useful for CI jobs.

### Add `.dot/` to `.gitignore`

Why: The `.dot` directory contains build artifacts and may include transient or sensitive data. Ignoring it prevents accidental commits, keeps diffs clean, and avoids polluting history.

### Add VSCode workspace settings for the `.dot` folder:

Why: Excluding `.dot` from VSCode search and file watcher keeps results noise‑free and prevents file handle locks that can interfere with commands like `dbt deps` when historical builds populate that directory. If you don't do this step, you may encounter errors when building.

Updated entries in `.vscode/settings.json` (created or merged if valid JSON):

```json
{
  "search.exclude": {
    "**/.dot": true,
    "**/.dot/**": true
  },
  "files.watcherExclude": {
    "**/.dot/**": true
  }
}
```

## Configuration Files

`dot` uses two project-level configuration files plus an optional user override:

1. `dot_vars.yml` (optional)  
   Defines variable specifications (metadata and validation). If absent, no variable validation (required/strict) occurs.
2. `dot_environments.yml` (optional)  
   Defines execution environments, default environment selection, dbt CLI argument values, and per‑environment variable value assignments.
3. `dot_environments.user.yml` (optional, uncommitted)  
   Adds or overrides environment definitions / variable assignments locally for a developer.

There is a strict separation:
- Variable *specifications* (description, allowed values, required, strict) live only in `dot_vars.yml`.
- Variable *values* are assigned only inside the `environment:` structure of the environments files (`dot_environments.yml` and optionally `dot_environments.user.yml`) under `environment.all.vars` or `environment.<name>.vars`.

### `dot_vars.yml` Example

```yaml
vars:
  feature_flag:
    description: Enables new metric logic
    values: [true, false]
    strict: true
    required: true
  sample_rate:
    description: Percentage of events to process
    values: [1, 5, 10, 25, 50, 100]
    strict: true
    required: false
```

### `dot_environments.yml` Example

```yaml
environment:
  default: dev
  all:
    indirect-selection: buildable
    vars:
      feature_flag: false
  dev:
    target: dev
    vars:
      sample_rate: 10
  prod:
    target: prod
    vars:
      feature_flag: true
      sample_rate: 100
```

### `dot_environments.user.yml` Example (Local Override)

```yaml
environment:
  dev:
    vars:
      feature_flag: true   # locally override baseline
    threads: 12
```

### Rules & Behavior

- All files are optional; absence yields default behavior (no environments, no validation).
- If `environment.default` is set it must name a defined environment.
- Variable validation (required / strict) is applied only to variables declared in `dot_vars.yml`.
- Undeclared variables assigned in environments are passed through without warnings or errors.
- User override merges shallowly with the project environments file; nested `vars` mappings are deep merged.

See:
- ADR 0002 for environment configuration & overrides
- ADR 0003 for variable specifications

## Isolated Builds

Isolated builds let you execute a dbt command against the exact contents of any git commit (or ref) in a clean, temporary worktree while writing all database objects into a schema that is namespaced by the commit hash. This provides:

- Reproducibility (build exactly what existed at that commit)
- Confidence to roll forward/back by inspecting isolated artifacts

Future features are planned to make more extensive use of isolated builds.

### Isolated Builds Quick Start

To build using the default environment specified in `dot_environments.yml` at a particular historical git reference, simply omit the environment and use `@<ref>`:

```sh
dot build @abc1234
```

Build an explicit environment against a ref:
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
<environment?>@<gitref>
```
- `environment` (optional) — name defined under `environment` in `dot_environments.yml`
- `gitref` (optional) — branch, tag, full/short hash, reflog expression, etc.
- If `@<gitref>` is supplied with no leading environment, the default environment is used.
- If no `@` suffix is provided, this is a normal (non‑isolated) build against the current state of your project.

### What Happens Internally

1. Resolve `<gitref>` to the full 40‑char commit hash and the abbreviated short hash via:
   - `git rev-parse <gitref>`
   - `git rev-parse --short <gitref>`
2. Construct: `.dot/build/<short_hash>/`
3. Create (or reuse) a clean git worktree at:
   ```
   .dot/build/<short_hash>/worktree/
   ```
4. Locate the dbt project inside that worktree matching the original project path.
5. Detect the active `profiles.yml` location (`dbt debug --config-dir`).
6. Read the selected profile + target (environment name).
7. Write an isolated `profiles.yml` to:
   ```
   .dot/build/<short_hash>/env/<environment>/profiles.yml
   ```
   with the target schema updated to `<schema>_<short_hash>`.
8. Set dbt CLI args so that:
   - `--project-dir` points at the isolated worktree project
   - `--profiles-dir` points at `.dot/build/<short_hash>/env/<environment>`
   - `--target-path` is `.dot/build/<short_hash>/env/<environment>/target`
   - `--log-path` is `.dot/build/<short_hash>/env/<environment>/logs`
9. Write the full hash to:
   ```
   .dot/build/<short_hash>/commit
   ```
10. Execute the dbt command.

### Schema Naming

The target schema becomes:

```
<original_schema>_<short_hash>
```

Where `<short_hash>` is the abbreviated commit hash reported by `git rev-parse --short <ref>` (length chosen automatically by git to avoid ambiguity). For example, if your original target schema is `analytics` and the short hash is `6b777b8c`, the isolated schema is:

```
analytics_6b777b8c
```

### Directory Layout

Example layout for an isolated build:

```
.dot/
  build/
    <short_hash>/           
      worktree/             
      commit                
      env/                  
        dev/
          profiles.yml      
          target/           
          logs/             
        prod/
          profiles.yml
          target/
          logs/
```

If you build multiple environments (`dev`, `prod`) for the same commit, each gets its own environment subdirectory under `env/`.

### Examples

Diff models between current development and a feature branch:
```sh
dot build dev
dot build dev@feature/new-metric
# Compare artifacts or query both schemas: analytics vs analytics_<short_hash>
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

`dot` invokes `dbt debug --config-dir` to locate the effective `profiles.yml`. It then:
- Loads the user’s configured profile
- Extracts the target matching the active environment
- Updates only the `schema` field (preserving credentials, threads, etc.)
- Writes a minimal isolated `profiles.yml` containing just that profile + target

### Automatic Dependency Installation for Isolated Builds

When you specify a git ref (either `env@ref` or just `@ref`) `dot` will automatically run `dbt deps` inside the isolated worktree before executing your requested primary dbt command.

Auto install is skipped when:
- You pass the `--no-deps` flag
- Your primary command is already `deps`
- You run with `--dry-run`

Skip dependency install:
```sh
dot --no-deps build dev@feature/my-branch
```

You can still run `dot deps dev@feature/my-branch` manually if desired.

### Cleanup

Currently there is no automatic cleanup. To reclaim space:
- Drop old schemas manually from your warehouse
- Remove stale directories under `.dot/build/`

### Troubleshooting

| Symptom | Cause | Action |
|---------|-------|--------|
| Error: Profile not found | Active environment or profile missing | Verify `profiles.yml` and environment name |
| Commit not found | Bad ref | Run `git show <ref>` to validate |
| Schema clutter | Many builds kept | Prune `.dot/build` & drop old schemas |
| Wrong default environment | Missing or unexpected `environment.default` | Set `default` under `environment` |

### Reference

For architectural rationale see: [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md).

## Deferred Builds (Commit-Based State Reuse)

`dot` supports reusing artifacts from a prior isolated build (an environment built at a specific git ref) as a baseline via dbt's deferral mechanism. This lets you skip re‑building upstream dependencies and focus on a subset of models while still guaranteeing reproducibility because the baseline is immutable (tied to a commit).

### Usage

```
dot build dev@HEAD --defer prod@main -- -s my_model+
dot test @HEAD --defer @main -- -s state:modified+
```

Valid --defer forms:

- `env@gitref`  – defer to environment `env` at git ref `gitref`
- `@gitref`     – defer to the default environment at git ref `gitref`


### What It Does

A command like:

```
dot build dev@HEAD --defer prod@main -- -s my_model
```

Resolves `prod@main` to the existing isolated build directory:

```
.dot/build/<short_hash(main)>/env/prod/target
```

and injects into the constructed dbt command:

```
--defer --favor-state --state .dot/build/<short_hash(main)>/env/prod/target
```

### Requirements

- The deferred baseline MUST already exist (run `dot build prod@main` first).
- The target directory must contain a valid `manifest.json`.
- Only commit-based (immutable) baselines are supported (ie: you must pass a gitref to --defer). 

### Rationale

Limiting defer to isolated builds at particular commits makes it a lot easier to reason about the current state of your project and helps to avoid errors. While it would be technically possible to allow defering to the current working directory, it does pose some problems when reasoning about the state of your project and database. If you think this would be useful please raise an issue or get in touch, I would love to hear your use case!

### Error Examples

| Spec | Error |
|------|-------|
| `--defer prod` | Must include a git ref |
| `--defer prod@` | Empty git ref |
| `--defer @` | Missing environment and git ref |
| Missing baseline directory | Instructs to build it first |

See the development plan (0005) for fuller design rationale.

## Architectural Decision Records

Architectural decisions are documented in the [adr/](adr/) directory.

- [ADR 0001: Isolated Builds](adr/0001-isolated-builds.md)
- [ADR 0002: Environment Configuration](adr/0002-environment-config.md)
- [ADR 0003: Variable Configuration (dot_vars.yml)](adr/0003-variable-config.md)

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for released versions.

## License

This project is licensed under the MIT License. See the `LICENSE` file for full details.

SPDX-License-Identifier: MIT
