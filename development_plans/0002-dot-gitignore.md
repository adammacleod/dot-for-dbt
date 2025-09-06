# Development Plan 0002: Enforce .gitignore for `.dot` Directory

Status: Complete

## Context

The `.dot` directory contains build artifacts and temporary files that should not be tracked by git. To prevent accidental commits and maintain repository hygiene, the CLI must ensure that `.dot` is properly ignored via `.gitignore`. This aligns with project standards and best practices outlined in [CONTRIBUTING.md](../CONTRIBUTING.md).

## Goals

- Ensure users have a `.gitignore` entry for `.dot` in the project root.
- CLI should check for the correct entry before running any commands.
- If missing, CLI should offer to insert the entry automatically.
- CLI must refuse to run if the entry is not present and the user declines insertion.
- Update documentation and tests to cover this behavior.

## Proposed Approach

1. **Detection**
   - On CLI startup, check if `.gitignore` exists in the git repository root.
   - Parse `.gitignore` to verify an entry for `.dot` or `.dot/` is present.

2. **Insertion Offer**
   - If missing, prompt the user to insert `.dot/` into `.gitignore`.
   - If accepted, append `.dot/` to `.gitignore`.

3. **Enforcement**
   - If the entry is still missing after prompt, abort CLI execution with a clear error.
   - Add a `--no-gitignore-check` CLI flag to bypass enforcement for advanced/CI use cases.

4. **Testing**
   - Add unit tests for detection, insertion, enforcement logic, and flag behavior.

5. **Documentation**
   - Update README.md and CONTRIBUTING.md to describe this requirement and the bypass flag.

## Progress

- [x] Context and goals defined
- [x] Proposed approach outlined
- [x] Implement detection logic in CLI
- [x] Implement insertion offer and enforcement
- [x] Add --no-gitignore-check flag to CLI
- [x] Add unit tests for new logic and flag
- [x] Update documentation (README.md, CONTRIBUTING.md)
- [x] Reference ADRs and this plan in docs
- [x] Final verification and close plan

## Risks and Mitigations

- **User confusion:** Provide clear CLI messaging and documentation.
- **Edge cases:** Handle variations like `.dot` vs `.dot/` and whitespace in `.gitignore`.
- **Cross-platform issues:** Ensure file path handling works on Windows, macOS, and Linux.

## Impact

- Prevents accidental commits of build artifacts.
- Improves repository hygiene and contributor experience.
- Adds a small but important check to CLI startup.
- Provides a bypass flag (`--no-gitignore-check`) for advanced workflows and CI.

## References

- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [ADR 0001: Isolated Builds](../adr/0001-isolated-builds.md)
- [gitignore documentation](https://git-scm.com/docs/gitignore)
- [Development Plans README](./README.md)
