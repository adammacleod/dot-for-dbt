# Development Plan 0004: User Prompts
Status: Completed  
Date: 2025-09-13  
Owner: dot tooling

## Context
The `.dot` directory is ignored via git (Plan 0002) but still indexed / watched by VSCode, causing noisy search results and file handle contention (especially on Windows). We need a consistent, extensible prompt framework to (a) enforce / suggest repository hygiene tasks (gitignore, editor settings) and (b) allow per‑feature and global opt‑out without state explosions.

## Goals
- Add (or offer to add) VSCode settings to exclude `.dot` from search & watchers.
- Re‑implement gitignore check using same unified prompt flow.
- Nested per‑feature enable/disable config (`prompts.gitignore`, `prompts.vscode`).
- Prompt tri-state interaction y / N / e (yes / no / never) with default = No.
- Abort on gitignore rejection unless user chooses “never” or feature disabled.
- Global suppression: `--disable-prompts` OR non-interactive TTY automatically skips all prompts & aborts.
- Idempotent, minimal file mutations; safe merges; no writes on parse failure.
- Modular registry for future prompt tasks.
- Comprehensive tests + docs + CHANGELOG.

## VSCode Required Settings
```
"search.exclude": {
  "**/.dot": true,
  "**/.dot/**": true
},
"files.watcherExclude": {
  "**/.dot/**": true
}
```

## Configuration Model (`.dot/config.yml`)
```
prompts:
  gitignore: enabled | disabled   # default if missing: enabled
  vscode:    enabled | disabled
```
Rules:
- Missing key → treated as enabled.
- “Never” selection sets that feature to disabled.
- Disabled ⇒ no prompt & (for gitignore) no abort enforcement.
- No extra states (no applied/history bookkeeping).

## Prompt Semantics
User input: `[y]es / [N]o / n[e]ver?`
- Enter / invalid ⇒ No.
- yes: perform action now (keep enabled).
- no: skip this run; may reappear.
- never (e): set `prompts.<feature>: disabled`; do not apply change (unless user first said yes).

## Precedence
1. Global disable (`--disable-prompts` or non-interactive)  
2. Feature disabled (`prompts.<feature>: disabled`)  
3. Interactive prompt (gitignore aborts on No; VSCode just skips)  

## Architecture
File: `cli_prompts.py`
- `PromptTask` dataclass:  
  - id  
  - detector() → COMPLIANT | NEEDS_ACTION | SKIP  
  - apply()  
  - message_builder()  
  - config_disable_key (e.g. `prompts.gitignore`)  
  - abort_on_no (bool)  
  - category (str)  
- Global registry `PROMPT_TASKS`.
- Runner:
  1. Evaluate global disable.
  2. For ordered tasks (gitignore first) run detector.
  3. If NEEDS_ACTION → prompt; interpret result; apply / abort / disable accordingly.
  4. Aggregate summary (APPLIED / SKIPPED / DISABLED / ABORTED).

## Gitignore Task (Refactor)
Detection: root `.gitignore` contains `.dot` or `.dot/`.  
If absent:
- Disabled/global → skip silently.
- Prompt:
  - yes: append `.dot/`.
  - no: abort (raise `PromptAbortError`).
  - never: set disabled & continue (no append).

## VSCode Task
Detection:
- Path: `.vscode/settings.json`.
- Parse:
  - If file missing ⇒ NEEDS_ACTION.
  - If present and strict JSON parse succeeds:
    - Verify required keys (merge dictionaries; preserve existing).
    - If any missing ⇒ NEEDS_ACTION else COMPLIANT.
  - If parse fails (JSONC / comments / trailing commas) ⇒ NEEDS_ACTION but on “yes” we DO NOT write; instead print manual snippet & allow “never” to disable.
Application:
- If creating: write minimal JSON containing only required blocks.
- If merging: update in-memory dict; write only if changes; preserve indentation (detect 2 vs 4 spaces), trailing newline.
- Never modify on parse failure; emit instructions.

## File Safety & Persistence
- Config load tolerant: YAML errors → warn, treat empty.
- Atomic config writes (temp + rename).
- Only persist changes when setting a feature to disabled (never).
- Do not record “applied”.

## Error Handling & Logging
- INFO: applied, skipped (disabled/global), manual action required.
- WARN: parse failures, permission issues.
- DEBUG: decision branches & precedence.
- Final summary emitted once.

## Non-Interactive Mode
`not sys.stdin.isatty()` ⇒ behave like `--disable-prompts` (no abort for gitignore).

## Testing Matrix (Representative)
Gitignore:
- Missing + yes ⇒ entry added.
- Missing + no ⇒ abort.
- Missing + never ⇒ disabled, no entry.
- Missing + disabled/global/non-interactive ⇒ no abort.
- Present (any state) ⇒ no action.

VSCode:
- Missing file + yes ⇒ file created with required keys.
- Missing file + no ⇒ none created.
- Missing file + never ⇒ no file, feature disabled.
- Partial + yes ⇒ keys merged.
- Already compliant ⇒ no write.
- Disabled/global/non-interactive ⇒ skipped.
- Corrupt / JSONC + yes ⇒ instructions only (no write); + never ⇒ disabled.
- Repeated run after “never” ⇒ no prompt.

Global:
- `--disable-prompts` ensures both tasks skipped; no abort.

Config:
- “never” sets key disabled; removing key re-enables.

## Documentation Updates
- README: New “Startup Prompts & Configuration” section with snippet and usage of `--disable-prompts`.
- CONTRIBUTING: How to add new prompt task (detector + apply + register).
- CHANGELOG: Feature entry (modular prompts, VSCode exclusion, unified gitignore flow).

## Risks & Mitigations
| Risk | Mitigation |
|------|------------|
| Overwriting custom VSCode formatting/comments | Abort write on parse failure; manual instructions instead. |
| User confusion y/N/e | Prompt string explicit; README examples. |
| Silent skips (global disable) | Emit final summary. |
| Repeated abort annoyance | Offer “never” path. |
| Corrupt config | Tolerant load + atomic save. |
| Drift after disabling gitignore | Doc clarifies disabling relinquishes enforcement. |

## Completion Criteria
- Framework & `cli_prompts.py` implemented.
- Nested config keys honored.
- y/N/e prompt + abort semantics.
- Gitignore flow migrated & passes tests.
- VSCode settings logic (merge, create, manual fallback) passes tests.
- Global disable & non-interactive behavior verified.
- Docs & CHANGELOG updated.
- Plan marked Completed.

## Progress
- [x] Context / goals / model defined
- [x] Architecture & precedence documented
- [x] Risks & tests enumerated
- [x] Implementation
- [x] Tests
- [x] Docs & CHANGELOG
- [x] Plan completion (mark Completed)

Implementation summary: Framework integrated (`cli_prompts.py`), gitignore + VSCode tasks registered, CLI flag `--disable-prompts` added, README/CONTRIBUTING/CHANGELOG updated, comprehensive tests for gitignore & VSCode (apply / decline / never / global disable / non-interactive / idempotency / invalid JSON manual path) added.

## References
- Plan 0002 (.gitignore)
- ADR 0001 (Isolated Builds)
- VSCode Settings Docs: https://code.visualstudio.com/docs/getstarted/settings

## Post-Completion Refinement (2025-09-13)
A follow-up refactor removed task-specific conditional logic from the generic `run_registered_prompts` runner:
- The legacy gitignore warning trio was relocated into `_gitignore_message()` as side-effect logging.
- Runner now treats all prompt tasks uniformly (no `if task.id == "gitignore"` branch).
- All 39 tests pass post-refactor (idempotency & behavior unchanged).
- No CHANGELOG update required (internal structural improvement only).

Rationale:
- Ensures strict separation of framework orchestration vs task presentation.
- Simplifies future task additions (no precedent for embedding special cases in runner).
- Preserves exact legacy messaging format and levels while centralizing responsibility within the task definition.
