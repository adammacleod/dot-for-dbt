# ADR 0003: Variable Configuration (dot_vars.yml)

## Status
Accepted

## Context
Variables used by dbt models/macros often need shared metadata: human descriptions, allowed values, and enforcement rules (required / strict enumerations). Previously this metadata co‑existed with environment configuration inside `dot_environments.yml`, increasing cognitive load and enabling drift between specification and usage. We have fully separated concerns:

- `dot_vars.yml` — authoritative variable specification (contract & validation metadata)
- `dot_environments.yml` (+ optional `dot_environments.user.yml`) — execution environments and variable value assignments

This ADR defines the variable specification model only. Environment merge / override semantics are covered by ADR 0002.

## Decision

### 1. File & Top-Level Structure
`dot_vars.yml` contains a single top-level key: `vars`.

```yaml
vars:
  <variable_name>:
    description: <string>        # Optional human-readable guidance
    values: [<allowed>, ...]     # Optional enumerated allowed values
    strict: true|false           # If true, assigned value must be one of values
    required: true|false         # If true, every resolved environment must define a value
```

Rules:
- Omission of the file ⇒ zero specs (no required / strict validation performed).
- Root-level keys other than `vars` are ignored for now and may become errors in future versions.
- Empty `vars:` mapping is valid.

### 2. Semantics of Fields
| Field | Meaning |
|-------|---------|
| description | Documentation / UX assist (non-functional) |
| values | Enumerated candidate values (advisory unless `strict: true`) |
| strict | Enforces membership in `values` when a value is assigned |
| required | Environment resolution must yield a value (either via `environment.all.vars` or a specific environment) |

No default value field exists. A “baseline” value (if desired) is assigned in `environment.all.vars` (ADR 0002).

### 3. Resolution & Validation Interaction
During environment resolution:
1. Variables file is parsed into an in‑memory spec map.
2. Environment value assignments are merged (project → user) as per ADR 0002.
3. For each spec:
   - If `required: true` and no effective value exists ⇒ error.
   - If `strict: true` and a value exists but not in `values` ⇒ error.
4. Variable assignments with no corresponding spec pass through unchanged (no warnings, no errors).

This keeps friction low while allowing incremental adoption of specifications.

### 4. Non‑Goals
- No type system beyond enumerations (future ADR may add types / patterns).
- No expression / templating language.
- No inline defaults in specs.
- No cross-variable dependency resolution.
- No multi-file layering for specs (single authoritative file only).

### 5. Example

`dot_vars.yml`:
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

`dot_environments.yml` (excerpt):
```yaml
environment:
  default: dev
  all:
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

Result:
- `feature_flag` validated as required & strict for both environments.
- `sample_rate` validated as strict where present; not required in all environments.

### 6. Error Conditions
| Condition | Error |
|-----------|-------|
| Non-mapping `vars` value | `'vars' in dot_vars.yml must be a mapping.` |
| Variable spec not a mapping | `Variable spec for '<name>' must be a mapping.` |
| Required variable missing | `Required variable '<name>' is not set for environment '<env>'.` |
| Strict enumeration violation | `Variable '<name>' has invalid value '<v>' for environment '<env>'. Allowed: [...]` |

### 7. Rationale
- Physical separation improves review clarity: operational changes do not mix with contract changes.
- Explicit contract enables future tooling (interactive editors, schema export).
- Opt-in spec model allows gradual hardening: teams can start with raw assignments and add specs over time.
- Avoiding defaults in specs eliminates ambiguity between “documentation” and “execution”.

### 8. Future Considerations
- Type system (int, float, string pattern, enum aliases).
- Schema export command (`dot config schema --json`).
- Optional warnings for assignments without specs (toggleable).
- Policy namespace (e.g. constraints on modification in certain environments).
- Variable grouping / categorization metadata.

## Consequences
Positive:
- Clear single source of truth for variable constraints.
- Enables better UX tooling and validation features.
- Keeps environment file focused on execution.

Trade-offs:
- Additional file to learn.
- Validation only applies where specs exist (intentional gradual adoption model).

## Summary
`dot_vars.yml` defines variable specifications—metadata and validation rules—completely decoupled from environment value assignment. Only declared variables incur required / strict enforcement; undeclared assignments remain flexible. This ADR is the authoritative specification for variable metadata in `dot`; operational merging and precedence live in ADR 0002.
