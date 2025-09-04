# Development Plan 0001: Isolated Builds

Status: Complete

## Context

This plan outlines the implementation of commit-isolated schemas for dbt builds, as described in [ADR 0001: Isolated Builds](../adr/0001-isolated-builds.md). The goal is to enable reproducible, isolated dbt builds for any git commit, supporting advanced workflows such as model diffing, robust deployments, and historical analysis.

## Goals

- Allow users to build dbt projects into schemas named after a short git commit hash (e.g., first 8 characters).
- Accept git refs (branches, tags, etc.) and resolve them to full commit hashes.
- Store all build artifacts (worktree, profiles.yml, target path) in a structured `.dot/<hash>/` directory.
- Ensure builds are reproducible and isolated from the main working directory.
- Support cleanup and management of old build artifacts.

## Proposed Approach

1. **Ref Resolution**
   - Use the [pygit2](https://www.pygit2.org/) Python library exclusively to resolve any git ref (branch, tag, or hash) to a commit hash.

2. **Worktree Management**
   - Use pygit2 to create a clean checkout at the resolved commit hash in `.dot/<hash>/worktree/`.
   - Ensure worktrees are created and removed safely.

3. **Schema Naming and Profiles**
   - Always build into a schema named `schema_<short_hash>`, where `<short_hash>` is the first 8 characters of the commit hash.
   - Generate a custom `.dot/<hash>/profiles.yml` targeting the correct schema.

4. **Target Path Isolation**
   - Use `.dot/<hash>/target/` as the dbt `--target-path` for all build outputs and manifests.

5. **CLI Integration**
   - Update or create CLI commands (e.g., `dc run dev@ref`) to orchestrate the above steps.

6. **Testing and Documentation**
   - Add tests for ref resolution, worktree management, and schema isolation.
   - Update documentation and usage examples.
   - Reference the ADR and this plan in project docs.

## Progress

- [x] Context and goals defined
- [x] Proposed approach outlined
- [x] ADR and development plan updated for short hash strategy
- [x] Implement ref resolution logic using pygit2 in src/dot/git.py
- [x] Add and update tests for ref resolution logic in tests/test_git.py
- [x] Require repo_path as Path type for resolve_git_ref
- [x] Move all git-related code to src/dot/git.py
- [x] Restore TODO.md to original content
- [x] Implement worktree management code for clean checkouts in .dot/<hash>/worktree/ (create_worktree)
- [x] Implement schema naming and profiles logic (.dot/<hash>/profiles.yml)
- [x] Integrate with CLI (e.g., dc run dev@gitref)
- [x] Implement target path isolation (.dot/<hash>/target/)
- [x] Update documentation, usage examples, ADR, and reference this plan in docs
- [x] Update CONTRIBUTING.md and README.md as needed
- [x] Verify results and finalize task

## Risks and Mitigations

- **Worktree Conflicts:** Ensure worktrees are managed safely to avoid conflicts or orphaned directories.
- **Schema Cleanup:** Implement robust cleanup to prevent orphaned schemas or excessive storage use.
- **Ref Resolution Errors:** Validate refs and handle errors gracefully.
- **Cross-Platform Compatibility:** Ensure commands work on all supported platforms (Windows, macOS, Linux).

## Impact

- Enables advanced workflows (diffing, red/green deployments, historical builds).
- Improves reproducibility and isolation of dbt builds.
- Adds complexity to build management and CLI tooling.
- Requires contributors to understand and manage `.dot/` artifacts.

## References

- [ADR 0001: Isolated Builds](../adr/0001-isolated-builds.md)
- [pygit2 documentation](https://www.pygit2.org/)
- [dbt profiles.yml documentation](https://docs.getdbt.com/docs/core/connect-data-platform/profiles.yml)
- [git worktree documentation](https://git-scm.com/docs/git-worktree)
- [Git refs and the reflog](https://www.atlassian.com/git/tutorials/refs-and-the-reflog)
