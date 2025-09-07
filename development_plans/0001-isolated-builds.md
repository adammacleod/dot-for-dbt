# Development Plan 0001: Isolated Builds

Status: Complete

## Context

We implement commit‑isolated dbt builds to achieve reproducibility, diffing, safe deployments, parallel environment testing, and deterministic artifact segregation. Using the full 40‑character commit hash in directory names unnecessarily inflates path length (notably on Windows when combined with nested dbt target artifacts). To mitigate path length risk while retaining traceability we key all filesystem artifacts by the unique short hash returned from `git rev-parse --short <ref>` (git auto‑expands if ambiguous).

The full 40‑character hash is still captured for audit and reverse mapping in a `commit` file inside each isolated build directory. No custom collision logic is required—git’s abbreviation mechanics guarantee uniqueness at resolution time or extend the abbreviation automatically.

## Goals

- Isolate every build in a clean worktree tied to an immutable commit.
- Use `git rev-parse --short <ref>` to derive `<short_hash>` (auto-expands when ambiguous).
- Use `<short_hash>` as the filesystem key: `.dot/build/<short_hash>/`.
- Name schemas `schema_<short_hash>`.
- Support multiple environments (e.g. dev, prod) per commit concurrently.
- Keep operations minimal: depend only on standard git CLI tooling.
- Rely on git auto-expanding abbreviations; no custom collision logic.
- Provide future hooks for pruning and metadata.

## Directory Layout

```
.dot/
  build/
    <short_hash>/
      worktree/                # Clean checkout at full commit
      env/                     # parent directory for environments
        <environment>/         # e.g. dev, prod
          profiles.yml         # schema: schema_<short_hash>
          target/              # dbt --target-path
          logs/                # dbt --log-path
      commit                   # file containing full 40-char hash
```

## Approach

1. Ref Resolution & Abbreviation
   - Run `git rev-parse --short <ref>` to get `<short_hash>`.
   - Run `git rev-parse <ref>` to obtain the full 40‑char hash if needed (e.g. metadata file).
   - Trust git’s abbreviation expansion for uniqueness.

2. Worktree Creation
   - Use `git worktree add --detach .dot/build/<short_hash>/worktree <full_hash>`.
   - Skip creation if directory already exists and is valid.
   - Removal (future pruning): `git worktree remove` or manual cleanup after ensuring no locks.

3. Collision Handling
   - No custom logic. If ambiguity exists git returns a longer abbreviation automatically; this yields a new isolated build directory.

4. Profiles Generation
   - Generate `.dot/build/<short_hash>/env/<environment>/profiles.yml` with schema `schema_<short_hash>`.
   - Keep logic centralized (e.g. in profiles module/function).

5. Artifact Isolation
   - `--target-path` → `.dot/build/<short_hash>/env/<environment>/target`
   - `--log-path` → `.dot/build/<short_hash>/env/<environment>/logs`

6. CLI Command Flow (e.g. `dot run dev@<ref>`)
   - Derive `<short_hash>` + full hash.
   - Ensure worktree present.
   - Generate profiles + environment directories.
   - Invoke dbt with isolated paths.

7. Commit Metadata
   - Store the full 40-char hash in `.dot/build/<short_hash>/commit` (mandatory for audit and reverse mapping).

8. Cleanup (Future)
   - Provide command to prune by age, count, or unused environments.

9. Testing
   - Unit: short hash derivation, directory scaffold (git auto-expands abbreviations).
   - Integration: end-to-end build creation for multiple refs & environments.
   - Path length sanity on Windows (ensure typical depths stay well below limits).

10. Documentation
    - ADR documents this approach.
    - README / CONTRIBUTING reference isolated builds and short hash rationale.

## Risks & Mitigations

- Abbreviation Collision: Handled automatically by git via longer abbreviation; separate directory is acceptable.
- Orphaned Artifacts: Future prune command.
- Windows Path Length: Short hash minimizes depth.
- Git Unavailability: Fail fast with clear error message.
- Manual Worktree Corruption: Validate presence of `.git` metadata; recreate if invalid.

## Impact

- Simpler dependency surface (no pygit2).
- Reproducible and parallelizable historical/environment-specific builds.
- No collision management code required.

## Completion Criteria

- Direct git CLI logic replaces all pygit2 references.
- Short hash directory scheme implemented.
- Worktrees & environment directories generated as specified.
- Tests updated/passing for new resolution path.
- ADR & this plan synchronized with direct git approach.
- CLI executes isolated build using short hash key.

## References

- `git rev-parse`
- `git worktree`
- dbt `profiles.yml`
- Git abbreviation mechanics (`git rev-parse --short`)
