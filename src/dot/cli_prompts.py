from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Dict, Optional, Any, List

from .logging import get_logger

logger = get_logger("dot.cli_prompts")

# ---------------------------------------------------------------------------
# Constants / Types
# ---------------------------------------------------------------------------

CONFIG_REL_PATH = Path(".dot") / "config.yml"
PROMPTS_ROOT_KEY = "prompts"

REPO_REQUIRED_VSCODE_SETTINGS = {
    "search.exclude": {
        "**/.dot": True,
        "**/.dot/**": True,
    },
    "files.watcherExclude": {
        "**/.dot/**": True,
    },
}

class DetectorResult(Enum):
    COMPLIANT = "COMPLIANT"
    NEEDS_ACTION = "NEEDS_ACTION"
    SKIP = "SKIP"

class PromptAbortError(Exception):
    """Raised when a mandatory prompt (gitignore) is declined."""

@dataclass
class PromptTask:
    id: str
    detector: Callable[[Path, Dict[str, Any], bool], DetectorResult]
    apply: Callable[[Path, Dict[str, Any]], None]
    message_builder: Callable[[], str]
    config_disable_key: str   # e.g. prompts.gitignore
    abort_on_no: bool = False
    category: str = "general"

# Registry
PROMPT_TASKS: List[PromptTask] = []

def register_prompt(task: PromptTask) -> None:
    PROMPT_TASKS.append(task)

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_prompts_config(repo_root: Path) -> Dict[str, Any]:
    cfg_path = repo_root / CONFIG_REL_PATH
    if not cfg_path.exists():
        return {}
    try:
        import yaml  # Local import to avoid cost if unused
        with cfg_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                logger.warning(f"[yellow]Ignoring malformed config at {cfg_path} (not a mapping).[/]")
                return {}
            return data
    except Exception as e:
        logger.warning(f"[yellow]Failed to read {cfg_path}: {e}. Treating as empty.[/]")
        return {}

def _save_prompts_config_atomic(repo_root: Path, data: Dict[str, Any]) -> None:
    cfg_path = repo_root / CONFIG_REL_PATH
    cfg_dir = cfg_path.parent
    cfg_dir.mkdir(parents=True, exist_ok=True)
    import yaml
    serialized = yaml.safe_dump(data, sort_keys=True)
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(cfg_dir)) as tmp:
            tmp.write(serialized)
            tmp_path = Path(tmp.name)
        tmp_path.replace(cfg_path)
    except Exception as e:
        logger.warning(f"[yellow]Failed to write config {cfg_path}: {e}[/]")

def _get_config_key(data: Dict[str, Any], dotted: str) -> Optional[Any]:
    parts = dotted.split(".")
    cur: Any = data
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur

def _ensure_mut_path(data: Dict[str, Any], dotted: str) -> tuple[Dict[str, Any], str]:
    parts = dotted.split(".")
    *parents, leaf = parts
    cur: Dict[str, Any] = data
    for p in parents:
        nxt = cur.get(p)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[p] = nxt
        cur = nxt
    return cur, leaf

def _set_config_value(data: Dict[str, Any], dotted: str, value: Any) -> None:
    parent, leaf = _ensure_mut_path(data, dotted)
    parent[leaf] = value

def feature_disabled(config: Dict[str, Any], key: str) -> bool:
    val = _get_config_key(config, key)
    return isinstance(val, str) and val.lower() == "disabled"

# ---------------------------------------------------------------------------
# Prompt mechanics
# ---------------------------------------------------------------------------

def prompts_globally_disabled(args: Any) -> bool:
    if getattr(args, "disable_prompts", False):
        return True
    if not sys.stdin.isatty():
        return True
    return False

def prompt_yes_no_never(question: str) -> str:
    """
    Return 'yes', 'no', or 'never'.
    Non-tty always returns 'no'.
    """
    if not sys.stdin.isatty():
        return "no"
    try:
        raw = input(f"{question} [y]es / [N]o / n[e]ver: ").strip().lower()
    except EOFError:
        return "no"
    
    raw = raw.lower()
    if raw in ("y", "yes"):
        return "yes"
    if raw in ("e", "never"):
        return "never"
    return "no"

# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def _gitignore_detector(repo_root: Path, config: Dict[str, Any], global_disabled: bool) -> DetectorResult:
    if global_disabled or feature_disabled(config, "prompts.gitignore"):
        return DetectorResult.SKIP
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.exists():
        # Treated as needs action (will abort or disable)
        return DetectorResult.NEEDS_ACTION
    try:
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line in (".dot", ".dot/"):
                    return DetectorResult.COMPLIANT
    except Exception:
        return DetectorResult.NEEDS_ACTION
    return DetectorResult.NEEDS_ACTION

def _vscode_detector(repo_root: Path, config: Dict[str, Any], global_disabled: bool) -> DetectorResult:
    if global_disabled or feature_disabled(config, "prompts.vscode"):
        return DetectorResult.SKIP
    vscode_settings = repo_root / ".vscode" / "settings.json"
    if not vscode_settings.exists():
        return DetectorResult.NEEDS_ACTION
    try:
        text = vscode_settings.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, dict):
            return DetectorResult.NEEDS_ACTION
    except Exception:
        # JSON parse failure (JSONC / invalid) -> still NEEDS_ACTION
        return DetectorResult.NEEDS_ACTION

    # Check required paths
    search_ex = data.get("search.exclude")
    watcher_ex = data.get("files.watcherExclude")
    if not isinstance(search_ex, dict):
        return DetectorResult.NEEDS_ACTION
    if not isinstance(watcher_ex, dict):
        return DetectorResult.NEEDS_ACTION

    need_keys = [
        ("search.exclude", "**/.dot"),
        ("search.exclude", "**/.dot/**"),
        ("files.watcherExclude", "**/.dot/**"),
    ]
    for section, key in need_keys:
        if section == "search.exclude":
            if search_ex.get(key) is not True:
                return DetectorResult.NEEDS_ACTION
        else:
            if watcher_ex.get(key) is not True:
                return DetectorResult.NEEDS_ACTION
    return DetectorResult.COMPLIANT

# ---------------------------------------------------------------------------
# Apply functions
# ---------------------------------------------------------------------------

def _gitignore_apply(repo_root: Path, _config: Dict[str, Any]) -> None:
    gitignore_path = repo_root / ".gitignore"
    try:
        if not gitignore_path.exists():
            gitignore_path.write_text(".dot/\n", encoding="utf-8")
            logger.info("Created .gitignore and added '.dot/' entry.")
            return
        with gitignore_path.open("r", encoding="utf-8") as f:
            existing = f.read()
        if ".dot" in existing:
            return
        with gitignore_path.open("a", encoding="utf-8") as f:
            if not existing.endswith("\n"):
                f.write("\n")
            f.write(".dot/\n")
        logger.info("Added '.dot/' to existing .gitignore.")
    except Exception as e:
        logger.warning(f"[yellow]Failed to modify {gitignore_path}: {e}[/]")

def _vscode_apply(repo_root: Path, _config: Dict[str, Any]) -> None:
    settings_path = repo_root / ".vscode" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if not settings_path.exists():
        # Create minimal JSON
        payload = {
            "search.exclude": REPO_REQUIRED_VSCODE_SETTINGS["search.exclude"],
            "files.watcherExclude": REPO_REQUIRED_VSCODE_SETTINGS["files.watcherExclude"],
        }
        settings_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        logger.info("Created .vscode/settings.json with required .dot exclusions.")
        return

    # Existing file -> attempt strict parse
    try:
        raw = settings_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except Exception:
        # Manual instructions path
        _emit_vscode_manual_instructions()
        return

    changed = False

    search_ex = data.get("search.exclude")
    if not isinstance(search_ex, dict):
        search_ex = {}
    for k, v in REPO_REQUIRED_VSCODE_SETTINGS["search.exclude"].items():
        if search_ex.get(k) is not True:
            search_ex[k] = True
            changed = True
    data["search.exclude"] = search_ex

    watcher_ex = data.get("files.watcherExclude")
    if not isinstance(watcher_ex, dict):
        watcher_ex = {}
    for k, v in REPO_REQUIRED_VSCODE_SETTINGS["files.watcherExclude"].items():
        if watcher_ex.get(k) is not True:
            watcher_ex[k] = True
            changed = True
    data["files.watcherExclude"] = watcher_ex

    if not changed:
        logger.debug("VSCode settings already compliant; no write performed.")
        return

    # Preserve indentation heuristic (2 vs 4)
    indent = 2
    if "\n    \"" in raw:
        indent = 4

    try:
        settings_path.write_text(json.dumps(data, indent=indent) + "\n", encoding="utf-8")
        logger.info("Updated .vscode/settings.json with required .dot exclusions.")
    except Exception as e:
        logger.warning(f"[yellow]Failed to update VSCode settings: {e}[/]")

def _emit_vscode_manual_instructions() -> None:
    snippet = json.dumps(REPO_REQUIRED_VSCODE_SETTINGS, indent=2)
    logger.warning(
        "[yellow]Could not parse existing .vscode/settings.json as strict JSON. "
        "Please ensure these keys exist (manual merge required):[/]\n"
        f"{snippet}"
    )
    # Also echo snippet to stdout so tests (capturing stdout) can assert visibility
    try:
        print(snippet)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

def _gitignore_message() -> str:
    # Emit legacy warnings (side-effect) before returning legacy prompt line.
    logger.warning("[bold yellow]WARNING: dot can potentially put sensitive information into the .dot folder within your repository.[/]")
    logger.warning(
        "It is very important that this folder is [bold]never[/] committed to git, "
        "therefore, [bold]dot[/] requires that the [italic].dot/[/] folder is "
        "ignored in your .gitignore file."
    )
    logger.warning("Note: You can skip this check with the --disable-prompts argument, but this is not recommended for general use.")
    return "         Would you like to add '.dot/' to your .gitignore now?"

def _vscode_message() -> str:
    logger.warning("[bold yellow]WARNING: If you use VSCode, it is recommended to exclude the .dot folder from search and the file watcher.[/]")
    logger.warning("Not setting this can cause a problem when building from old commits, as VSCode will hold a file handle open on files in the .dot directory, preventing `dbt deps` from running.")
    return (
        "         Add/edit .vscode/settings.json to exclude '.dot'?"
    )

# ---------------------------------------------------------------------------
# Framework execution
# ---------------------------------------------------------------------------

def run_registered_prompts(repo_root: Path, args: Any) -> None:
    """
    Execute prompt workflow according to precedence.
    """
    config = _load_prompts_config(repo_root)
    global_disabled = prompts_globally_disabled(args)

    ordered = sorted(PROMPT_TASKS, key=lambda t: 0 if t.id == "gitignore" else 1)

    summary: list[tuple[str, str]] = []  # (task_id, result)

    for task in ordered:
        # Precedence: global disable
        if global_disabled:
            summary.append((task.id, "SKIPPED (global)"))
            continue

        if feature_disabled(config, task.config_disable_key):
            summary.append((task.id, "DISABLED"))
            continue

        result = task.detector(repo_root, config, global_disabled)
        if result == DetectorResult.COMPLIANT:
            summary.append((task.id, "COMPLIANT"))
            continue
        if result == DetectorResult.SKIP:
            summary.append((task.id, "SKIPPED"))
            continue

        # NEEDS_ACTION
        
        decision = prompt_yes_no_never(task.message_builder())
        if decision == "yes":
            try:
                task.apply(repo_root, config)
                summary.append((task.id, "APPLIED"))
            except Exception as e:
                logger.warning(f"[yellow]Failed applying task {task.id}: {e}[/]")
                summary.append((task.id, "FAILED"))
                if task.abort_on_no:
                    # treat as abort since mandatory
                    raise PromptAbortError(f"Mandatory task {task.id} failed.")
        elif decision == "never":
            _set_config_value(config, task.config_disable_key, "disabled")
            _save_prompts_config_atomic(repo_root, config)
            summary.append((task.id, "DISABLED (never)"))
        else:  # 'no'
            if task.abort_on_no:
                summary.append((task.id, "ABORTED"))
                raise PromptAbortError(f"Mandatory task [bold]{task.id}[/] declined by user.")
            summary.append((task.id, "SKIPPED (declined)"))

    # Summary
    if summary:
        parts = [f"{tid}={res}" for tid, res in summary]
        logger.debug(f"[bold]Prompt summary:[/] {', '.join(parts)}")

# ---------------------------------------------------------------------------
# Task registration
# ---------------------------------------------------------------------------

register_prompt(
    PromptTask(
        id="gitignore",
        detector=_gitignore_detector,
        apply=_gitignore_apply,
        message_builder=_gitignore_message,
        config_disable_key="prompts.gitignore",
        abort_on_no=True,
        category="hygiene",
    )
)

register_prompt(
    PromptTask(
        id="vscode",
        detector=_vscode_detector,
        apply=_vscode_apply,
        message_builder=_vscode_message,
        config_disable_key="prompts.vscode",
        abort_on_no=False,
        category="editor",
    )
)
