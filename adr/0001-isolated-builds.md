# ADR 0001: Isolated Builds

## Status

Accepted

## Context

To enable advanced workflows such as model diffing, reproducible builds, and robust deployment strategies, we want to build dbt projects into database schemas named after the git commit hash. Users may specify a git ref (branch, tag, etc.), but this will always be resolved to a commit hash using `git rev-parse`. To keep schema names manageable, we will use a short hash (e.g., the first 8 characters of the commit hash) for naming schemas (e.g., `schema_<short_hash>`), while still resolving refs to the full hash for correctness. This ensures reproducibility and avoids ambiguity, since refs can change over time.

## Decision

- All artifacts related to isolated builds are contained within the `.dot` directory in the project root. For each build:
  - `.dot/isolated_builds/<hash>/worktree/` contains the clean checkout created by `git worktree` at the resolved commit hash.
  - `.dot/isolated_builds/<hash>/<context>/profiles.yml` is a custom profiles file targeting `schema_<short_hash>`.
  - `.dot/isolated_builds/<hash>/<context>/target/` is used as the dbt `--target-path` for build outputs and manifests.
  - `.dot/isolated_builds/<hash>/<context>/logs/` is used as the dbt `--log-path` for logs for runs in this isolated build

- Where possible we should use the [pygit2](https://www.pygit2.org/) Python library for portability, maintainability, and consistency. Although in some instances we might need to call a subprocess to `git` directly.

- When running `dc run dev@ref`, the system will:
  - Resolve the provided git ref (branch, tag, or hash) to a commit hash using pygit2.
  - Use pygit2 to create a clean, isolated working tree at `.dot/isolated_builds/<hash>/worktree/`.
  - Build the dbt project in this worktree, targeting a schema named `schema_<short_hash>`, using the profiles.yml file from `.dot/isolated_builds/<hash>/<context>/profiles.yml`.
  - Use dbt's `--target-path .dot/isolated_builds/<hash>/<context>/target` to isolate manifest/output files per environment.

**Example directory structure for a build at <commit>:**

```
.dot/
  isolated_builds/
    <commit>/          # All code and artifacts required for isolated build of <commit>
      worktree/        # A clean checkout of the repository at the commit
      <context>/       # Files which are specific to particular contexts (ie: dev/prod)
        profiles.yml   # Auto-generated profiles.yml, which sets schema: <schema>_<short_hash>
        target/        # Output artifacts for this commit and context
        logs/          # dbt logs generated during the isolated build
```

## Consequences

- Enables building and testing any historical version of the project without polluting the main working directory.
- All artifacts for isolated builds are organized and contained within the `.dot` directory, simplifying cleanup and management.
- Supports diffing models between arbitrary commits or refs by building both into separate schemas.
- Facilitates red/green deployments and safe rollbacks.
- Ensures that schemas are always tied to immutable commit hashes, avoiding ambiguity from moving refs.
- Keeps schema names short and manageable by using a short hash, while maintaining uniqueness and traceability.
- Requires management of multiple worktrees and schemas, including cleanup of old resources in `.dot`.
- Custom logic is needed to resolve refs (using pygit2), generate and manage `.dot/isolated_builds/<commit>/*`.

## Alternatives Considered

- Allowing schemas to be named after refs (branches/tags), but this would introduce ambiguity since refs can move and would not guarantee reproducibility.
- Overriding `target_schema` at runtime (not feasible without custom profiles).
- Using a single schema and overwriting contents (loses isolation and reproducibility).

## References

- [pygit2 documentation](https://www.pygit2.org/)
- See dbt documentation on [profiles.yml](https://docs.getdbt.com/docs/core/connect-data-platform/profiles.yml) and [git worktree](https://git-scm.com/docs/git-worktree).
- There is a great writeup of git refs [here](https://www.atlassian.com/git/tutorials/refs-and-the-reflog)
