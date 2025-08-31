# dot - The Data Orchestration Tool

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

## Architectural Decision Records

Architectural decisions are documented in the [adr/](adr/) directory.

- [ADR 0001: Commit Isolated Schemas for dbt Builds](adr/0001-commit-isolated-schemas.md)

## Isolated Schema Builds

When generating a `profiles.yml` for isolated schema builds, dot now automatically detects the location of your `profiles.yml` using the output of `dbt debug`. It loads the relevant profile and updates the schema for the build context.
