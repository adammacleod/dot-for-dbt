# dot - The Data Orchestration Tool

## vars.yml Behavior

- `vars.yml` is optional. If it does not exist in your working directory, dot will proceed with default settings and no context-based variables.
- If `vars.yml` exists but is malformed (invalid YAML), dot will print an error and exit.
- If you specify a context that does not exist in `vars.yml`, dot will print an error and exit.
- If no context is specified and no default is set in `vars.yml`, dot will proceed with default settings.

## Architectural Decision Records

Architectural decisions are documented in the [adr/](adr/) directory.

- [ADR 0001: Commit Isolated Schemas for dbt Builds](adr/0001-commit-isolated-schemas.md)
