# ADR 0002: Environment Configuration (dot_environments.yml)

## Status
Accepted

## Context
`dot` needs a deterministic, minimal way to declare dbt execution environments plus a per‑developer override layer. Variable *specifications* (metadata / validation rules) are now handled separately in `dot_vars.yml` (see ADR 0003). This ADR defines only the environments configuration model and its override semantics.

## Decision

### 1. Files & Layers
Lowest precedence first:
1. Project Environments File (committed): `dot_environments.yml`
2. User Environments Override (uncommitted): `dot_environments.user.yml`

No global (multi‑repository) user layer is provided. The user file must be `.gitignore`d.

### 2. Top-Level Structure (Environments File)
```yaml
environment:
  default: <env_name>          # Optional default environment name
  all:                         # Optional arguments applied to every environment
    <dbt_arg>: <value>
    vars:
      <variable_name>: <value>
  <env_name>:
    <dbt_arg>: <value>
    vars:
      <variable_name>: <value>
```

Rules:
- Only one top-level key is currently recognized: `environment`.
- Root-level `vars:` is invalid here (variable specifications now live in `dot_vars.yml`).
- Omission of the file or of `environment:` yields “no configured environments” (commands may still run without environment context).
- Values under each environment (except `vars`) are treated as candidate dbt CLI arguments; a filtering allow‑list is applied later.

### 3. Variable Value Assignments
Execution values for variables are assigned only under:
- `environment.all.vars`
- `environment.<name>.vars`

Whether a variable has metadata (description / required / strict / values) depends on the optional presence of a specification in `dot_vars.yml`. Undeclared variables can still be assigned freely (no validation imposed).

### 4. Merge & Precedence
Merge order: project file → user file (user overrides project).

Shallow merge semantics with one targeted deep merge:
| Section | Strategy |
|---------|----------|
| `environment.default` | Last non-null wins |
| `environment.all` | Shallow merge of keys; deep merge of nested `vars` mapping |
| `environment.<name>` | Shallow merge of keys; deep merge of nested `vars` mapping |
| Unknown future top-level keys | Replaced wholesale by the later layer (until specialized) |

Deep merge of `vars` allows a user override to amend or add a single variable without duplicating the entire mapping.

### 5. Validation (Environments Scope)
Performed after merging:
1. If `environment.default` is set it must correspond to a defined environment key.
2. Each environment body (including `all`) must be a mapping.
3. Any `vars` present inside `all` or an environment must be a mapping.
4. Root-level `vars` key in either environments file is a hard error (enforces clean separation from ADR 0003).
5. Other structural anomalies raise `ConfigError`.

Variable-specific validation (required / strict / allowed values) is defined in ADR 0003 and applied only to variables that have a specification there.

### 6. Resolution Model
Resolving an environment (default or explicitly named):
1. Start with empty args / vars
2. Merge project `environment.all` (args + vars)
3. Merge project named environment (args + vars)
4. Merge user `environment.all` (args + vars)
5. Merge user named environment (args + vars)
6. Filter args by dbt command allow‑list (per command)
7. Attach merged vars (unfiltered)

If no environments are configured and none requested, an empty environment spec is returned.

### 7. Public API (Excerpt)
(Shared with variable specs handling; shown here for context.)
```python
load_config(project_root: Path) -> DotConfig
resolve_environment(cfg: DotConfig, name: Optional[str]) -> DotEnvironmentSpec
dbt_cli_args(dbt_command: str, env_spec: DotEnvironmentSpec) -> dict[str, Any]
```
`DotConfig` now contains:
- `variables` (from ADR 0003; may be empty)
- `default_environment`
- `project_environments` (original project file `environment` mapping)
- `user_environments` (original user override file `environment` mapping)

### 8. Non‑Goals
- No hierarchical environment inheritance beyond `all` + named env.
- No implicit variable defaults (must be explicitly assigned under `all` or a specific env).
- No expression / templating engine.
- No global user layer (future ADR if ever needed).
- No automated cleanup logic for build artifacts, for now.

### 9. Example
`dot_environments.yml`:
```yaml
environment:
  default: dev
  all:
    indirect-selection: buildable
    vars:
      feature_flag: false
  dev:
    target: dev
  prod:
    target: prod
    vars:
      feature_flag: true
```

`dot_environments.user.yml`:
```yaml
environment:
  dev:
    vars:
      feature_flag: true   # locally override the value
    threads: 12
```

Result (dev):
- args: `indirect-selection=buildable`, `target=dev`, `threads=12`
- vars: `feature_flag=true`

### 10. Rationale
- Separation of *specification* (ADR 0003) from *assignment* keeps environment file concise and operationally focused.
- Deep merge only for `vars` reduces duplication and risk of accidental overwrites.
- Deterministic precedence enables reproducible runs and simpler debugging.
- For contributors, a predictable, single-purpose file improves review clarity.

### 11. Future Considerations
- Additional namespaces (e.g. `policy:`) for execution constraints or pruning.
- Optional global layer (if real multi-project reuse demand appears).
- Advisory / diagnostic reporting (e.g. detect unused variables or unreachable environments).
- Caching & incremental validation.

## Consequences
Positive:
- Lean environment file—only operational settings.
- Clear mental model: “specs vs assignments” physically separated.
- Simple override workflow; minimal duplication.

Trade-offs:
- One more file introduced (slight overhead).
- Need cross-reference with ADR 0003 for variable metadata context.

## Summary
`dot_environments.yml` (plus optional `dot_environments.user.yml`) defines dbt execution environments and variable *assignments*. Variable *specifications* are exclusively defined in `dot_vars.yml` (ADR 0003). Environments merge shallowly except for a deep merge of nested `vars` mappings; validation ensures structural integrity and default environment correctness. This ADR is the authoritative specification for environment configuration and precedence.
