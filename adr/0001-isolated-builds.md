# ADR 0001: Isolated Builds

## Status

Accepted

## Context

We require reproducible, isolated dbt builds bound immutably to specific git commits to support historical comparisons, diffing, safe deployments, and parallel environment testing. Builds must not pollute the working tree and all generated schemas and artifact paths must be deterministic and segregated.

Using the full 40‑character commit hash in directory names unnecessarily increases path length (notably problematic on Windows). Git’s built‑in abbreviated hash (`git rev-parse --short <ref>`) is already unique at the time of resolution (auto‑expanding if needed). Therefore we key all on‑disk build artifacts by the short hash while storing the full hash separately for audit and reverse mapping.

## Decision

We will use the short commit hash (as returned by `git rev-parse --short <ref>`) as the canonical on-disk identifier for isolated build directories and related resources. The git CLI alone is sufficient for ref resolution and abbreviation; no additional git bindings are required.

- Directory layout (per commit + context):
  - `.dot/build/<short_hash>/worktree/` — clean checkout (created via `git worktree add`) at the resolved full commit.
  - `.dot/build/<short_hash>/commit` — file containing the full 40‑character commit hash.
  - `.dot/build/<short_hash>/<context>/profiles.yml` — generated profiles file targeting schema `schema_<short_hash>`.
  - `.dot/build/<short_hash>/<context>/target/` — dbt `--target-path`.
  - `.dot/build/<short_hash>/<context>/logs/` — dbt `--log-path`.

- Ref & Hash Handling:
  - User supplies a git ref (branch, tag, or hash).
  - We obtain the unique short hash directly via `git rev-parse --short <ref>` (git auto-expands if ambiguous).
  - When the full 40‑character hash is required (audit/metadata) we call `git rev-parse <ref>`.
  - We store and index isolated builds by `<short_hash>` only.

- Schema Naming:
  - Always `schema_<short_hash>` to keep identifiers compact while preserving traceability.

- Uniqueness & Collisions:
  - Rely solely on git’s abbreviation guarantees; if ambiguity exists git emits a longer abbreviation automatically and a new isolated build directory is created. No custom collision or migration logic.

- Implementation:
  - Use only core git CLI commands: `git rev-parse`, `git worktree add`, and `git worktree remove` (or manual cleanup).
  - Write the full 40-character hash to `.dot/build/<short_hash>/commit` for audit and reverse mapping.

**Example structure:**
```
.dot/
  build/
    3fa12c9/                # short hash identifier
      worktree/             # clean checkout at full commit
      commit                # full 40-char commit hash
      dev/
        profiles.yml        # schema: schema_3fa12c9
        target/
        logs/
      prod/
        profiles.yml
        target/
        logs/
```

## Consequences

- Reduced path lengths (mitigates Windows path limit risks).
- Maintains reproducibility: short hash deterministically identifies a single commit at build time.
- Easier navigation and cleaner filesystem footprint.
- Enables concurrent isolated builds for different commits and contexts.
- Eliminates dependency on external git libraries (simpler runtime + fewer transitive issues).
- External tooling expecting full hashes must map via stored metadata or `git rev-parse`.

## Future Considerations

- Automated pruning policies for stale isolated builds.

## References

- `git rev-parse` documentation
- `git worktree` documentation
- dbt `profiles.yml` configuration
- Git abbreviation behavior (`git rev-parse --short`)
