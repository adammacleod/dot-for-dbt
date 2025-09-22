# Development Plan 0005: Deferred Builds (dbt --defer Integration)

Status: Completed  
Date: 2025-09-16  
Owner: dot build tooling

## Context

dbt's defer mechanism lets a run treat upstream nodes as already built by pointing at prior run artifacts via:

```
--defer --favor-state --state <state_dir>
```

`<state_dir>` must contain prior dbt artifacts (`manifest.json`, `run_results.json`, etc).  
`dot` already produces **isolated build artifacts** keyed by commit short hash:

```
.dot/build/<short_commit_hash>/env/<environment>/
  target/
  logs/
  profiles.yml
  commit        # full 40-char hash
```

We want a first‑class CLI interface to select a prior isolated build (environment + git ref) as the deferral baseline without the user manually constructing the state path.

Example target usage:

```
dot build dev@HEAD --defer prod@main -- -s some_selector
dot test  @HEAD  --defer @main
```

## Goals

- Provide `--defer <spec>` where `<spec> ::= [<environment>]@<gitref>` or `@<gitref>` (git ref **mandatory**).
- Accept two valid patterns:
  - `env@ref` → defer to environment `env` at commit-ish `ref`
  - `@ref` → defer to the default environment at commit-ish `ref`
- Reject all forms lacking a git ref (e.g. `env`, `env@`, `@`).
- Translate spec into dbt flags: `--defer --favor-state --state <resolved_isolated_target_dir>`.
- Reuse existing git ref resolution & isolated build layout (no duplication).
- Extract existing environment@gitref parsing into a shared helper (`parse_env_gitref`) used by both primary environment argument and defer spec.
- Perform early validation (environment existence, git ref resolvability, presence of `manifest.json`).
- Do not auto-build missing baselines; instruct user how to create them.
- Provide clear, actionable error messages.
- Add comprehensive tests (parsing, resolution, failure modes, command assembly).
- Update README, CONTRIBUTING, CHANGELOG.

## Design Decision: Commit-Based Deferral Only

Workspace (mutable) environment targets are **excluded** from the initial implementation. All deferral baselines must be tied to an immutable git ref to preserve reproducibility, debuggability, CI parity, and clear provenance. Any `--defer` spec that omits a git ref (e.g. `--defer prod`, `--defer prod@`) will be rejected with guidance to use `prod@<gitref>` or `@<gitref>` (default environment). Support for mutable workspace deferral may be reconsidered later if a demonstrated need emerges.

## Out of Scope (Initial Version)

- Workspace / mutable baseline deferral.
- Auto-creating missing baseline builds.
- Multiple / chained / fallback deferral baselines.
- Arbitrary user-supplied `--state` path override.
- Performance optimizations beyond current isolated build workflow.

## Argument Grammar & Semantics

`--defer <spec>`

Valid forms:

| Spec | Meaning |
|------|---------|
| `env@ref` | Defer to environment `env` artifacts from isolated build at git ref `ref`. |
| `@ref` | Defer to default environment artifacts from isolated build at git ref `ref`. |

Invalid (error):

| Spec | Reason |
|------|--------|
| `env` | Missing git ref (workspace deferral unsupported). |
| `env@` | Empty git ref. |
| `@` | Missing both environment and git ref. |
| `a@b@c` | Multiple `@` separators. |

## Resolution Rules

1. Parse with shared `parse_env_gitref` (split on first `@`; reject multiple).
2. Require a non-empty git ref. If missing → error.
3. If environment missing, use configured default (error if none).
4. Validate environment exists (reuse config resolution mechanics).
5. Resolve full & short commit hash via git helpers (`get_full_commit_hash`, `get_short_commit_hash`).
6. Construct path:  
   `.dot/build/<short_hash>/env/<env>/target`
7. Validate presence of directory AND `manifest.json`.
8. Inject dbt flags (`--defer --favor-state --state <path>`).

## Failure Cases & Messages (Draft)

| Condition | Error Message |
|-----------|---------------|
| Missing git ref | "`--defer` spec must include a git ref (use env@<gitref> or @<gitref>). Workspace deferral is not supported." |
| Missing environment and no default configured | "Cannot infer defer environment: no default environment configured." |
| Unknown environment | "Defer environment '<env>' not defined in configuration." |
| Unresolvable git ref | Propagate underlying git error (prefixed with `git ref resolution failed:`). |
| Missing isolated build directory | "Deferred state not found at <path>. Run: dot build <env>@<gitref> first." |
| Missing manifest.json | "Deferred state path <path> missing manifest.json (incomplete or never built?)." |
| Multiple @ | "`--defer` spec '...' is invalid: multiple '@' separators." |

## Integration Points

Current path:
`cli.app()` → parse arguments (environment token may include `@gitref`) → maybe run deps for isolated build → build dbt command.

Additions:
- New optional argument `--defer`.
- After primary environment/gitre f parsing, parse defer spec (if provided).
- Resolve & validate baseline; no mutation if invalid (fail early).
- Pass `defer_path` (Path) into `dot.dbt_command`.
- Inside `dot.dbt_command`, when `defer_path` is provided:
  - Add `defer=True`, `favor-state=True`, `state=<defer_path>` to environment args before filtering.

## Proposed Approach

1. **Parsing**
   - Factor existing environment@gitref parse logic from `cli.app()` into `parse_env_gitref(spec) -> (env_or_none, ref_or_none)`.
   - Add CLI arg:  
     ```
     parser.add_argument("--defer", dest="defer_spec",
                         metavar="ENV@GITREF or @GITREF",
                         help="Defer to artifacts from isolated build (git ref required).")
     ```
2. **Validation & Resolution**
   - Implement `resolve_defer(repo_root, cfg, env_name_or_none, gitref) -> Path`:
     - Infer environment.
     - Validate environment membership.
     - Resolve hashes; compute `.dot/build/<short_hash>/env/<env>/target`.
     - Assert existence + `manifest.json`.
3. **Command Assembly**
   - Extend `dbt_command(..., defer_path: Optional[Path])`.
   - Inject flags pre-allow‑list.
4. **Allow-list Update**
   - Ensure `--state` and `--favor-state` included for commands supporting `--defer` (currently build, run, test). Add if missing.
5. **Errors**
   - Raise `ValueError`; caught in `cli.app()` with consistent messaging.
6. **Documentation**
   - README: New section “Deferring to Prior Builds (Immutable Baselines)”.
   - Explicitly note unsupported workspace baseline.
7. **CHANGELOG**
   - Feature entry with usage examples & rationale.
8. **Tests**
   - Parsing: valid/invalid patterns.
   - Resolution: success & each failure path (mock git where needed).
   - Command assembly: final arg list includes flags & correct state path.
   - Negative: `--defer prod` returns error about missing git ref.

## Data Flow Example

```
dot build dev@abc123 --defer prod@def456 -- -s tag:incremental

Primary: env=dev, gitref=abc123 (isolated build created/ensured)
Defer:   env=prod, gitref=def456
State:   .dot/build/<short(def456)>/env/prod/target

Final:
dbt build ... --defer --favor-state --state .dot/build/<short(def456)>/env/prod/target -s tag:incremental
```

## Alternatives Considered (Rejected)

| Alternative | Reason |
|-------------|--------|
| Support workspace (no git ref) defer | Non-deterministic, lower reproducibility, added complexity. |
| Auto-build missing baseline on demand | Hides intent; unexpected side effects; less explicit CI parity. |
| Accept raw `--state` path | Expands surface area; less guided; postpone until explicit need. |
| Separate flag name (`--defer-to`) | Diverges from dbt’s native semantics; no added clarity. |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| User confusion about rejected `--defer env` | Clear error with remediation (use env@<ref>). |
| Large number of isolated builds accumulating | Future pruning command (already considered in earlier plans). |
| Path length on Windows | Short hashes keep paths concise. |
| Partial baseline (missing manifest) | Explicit pre-run validation. |
| Divergence if dbt adds new defer-related flags | Centralize flag injection; extend allow-list when needed. |

## Impact

- Adds reproducible cross-environment comparison / state reuse.
- No behavioral change for users not invoking `--defer`.
- Minor complexity increase (one parsing helper + validation function).
- Strengthens alignment with isolated build philosophy (ADR 0001).

## Testing Strategy

Unit:
- `parse_env_gitref("prod@abc") -> ("prod","abc")`
- `parse_env_gitref("@abc") -> (None,"abc")`
- Invalid: `"prod"`, `"prod@"`, `"@"`, `"a@b@c"`.
- Defer resolution success (mock build tree).
- Failure coverage for each error condition.

Integration:
- `dot build dev@HEAD --defer prod@HEAD~1 -- -s model` includes expected flags.
- `dot test @HEAD --defer @HEAD~2` uses default environment.
- `--defer prod` fails with missing git ref message.

Edge:
- Same env/ref for active and defer (allowed; still injects flags).
- Unknown env in defer spec (error).
- Ambiguous short ref (git auto-expands; test with mock).

## Implementation Tasks (Progress Checklist)

- [x] Extract environment@gitref parsing helper (`parse_env_gitref`)
- [x] Add `--defer` CLI argument (gitref required conceptually)
- [x] Implement deferral resolution (inline in cli.app(); helper extraction deferred)
- [x] Update `DBT_COMMAND_ARGS` to include `--state`, `--favor-state` where `--defer` allowed
- [x] Extend `dot.dbt_command` to accept `defer_path`
- [x] Inject flags (`--defer --favor-state --state`) when baseline resolved
- [x] Add validation & error messages
- [x] Unit tests (add cases: multiple '@' invalid spec, missing manifest.json baseline, unresolvable git ref)
- [x] Integration tests (assert flags `--defer --favor-state --state` and correct state path)
- [x] README updates (feature section)
- [x] CONTRIBUTING updates (development notes)
- [x] CHANGELOG entry
- [x] Final review & mark plan Completed

## Documentation Snippet (Draft)

```
### Deferred Builds (Immutable Only)

Use artifacts from a prior isolated build as a state baseline:

dot build dev@HEAD --defer prod@main -- -s state:modified+
dot test @HEAD --defer @main -- -s some_model

Spec forms:
  env@ref  (explicit environment)
  @ref     (default environment)

Forms without a git ref (env, env@) are not supported.  
If missing baseline: first run an isolated build, e.g. dot build prod@main.

Transforms into:
  --defer --favor-state --state .dot/build/<short_hash(ref)>/env/<env>/target
```

## References

- ADR 0001: Isolated Builds
- dbt docs: defer, state, favor-state
- Existing internal modules: `git.py`, `dot.py`, `config.py`

## Open Questions (Future Consideration)

- Add optional workspace defer with explicit opt-in flag?
- Provide `--state-path` override?
- Baseline pruning policy / command?

(Any future expansion will amend this plan or introduce a follow-up plan.)
