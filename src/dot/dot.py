import json
from pathlib import Path
from typing import Any, Optional, List

from . import logging
from .logging import get_logger
from .profiles import write_isolated_profiles_yml
from .git import (
    create_worktree,
    get_repo_path,
    get_full_commit_hash,
    get_short_commit_hash,
)

from .config import (
    load_config,
    resolve_environment,
    ConfigError,
    DBT_COMMAND_ARGS,
)

logger = get_logger("dot.dot")

def dbt_command(
    dbt_command_name: str,
    dbt_project_path: Path,
    active_environment: Optional[str],
    passthrough_args: Optional[list[str]] = None,
    gitref: Optional[str] = None,
    defer_path: Optional[Path] = None,
) -> list[str]:
    """
    Construct a dbt CLI command as a list of arguments using the new configuration
    model defined in ADR 0002.

    This:
      1. Loads dot_environments.yml (+ optional local override).
      2. Resolves the selected (or default) environment.
      3. Builds allowed dbt CLI arguments (including --vars JSON).
      4. If a gitref is supplied, performs an isolated build checkout and rewrites
         profiles + target/log paths accordingly.

    Args:
        dbt_command_name: The dbt subcommand to run (e.g. 'run', 'test').
        dbt_project_path: Path to the dbt project root (must contain dbt_project.yml).
        active_environment: Name of the environment to use (may be None -> default).
        passthrough_args: Extra args after '--' passed directly to dbt.
        gitref: Optional git ref / commit hash for isolated build.
        defer_path: Optional path to a prior isolated build target directory used for dbt --defer --state <defer_path>.

    Returns:
        List[str]: The dbt command argument list suitable for subprocess execution.
    """
    passthrough_args = passthrough_args or []

    if not (dbt_project_path / "dbt_project.yml").exists():
        raise ValueError(f"dbt_project.yml not found in: {dbt_project_path}")

    # Load & resolve configuration
    try:
        cfg = load_config(dbt_project_path)
        env_spec = resolve_environment(cfg, active_environment)
    except ConfigError as e:
        raise ValueError(str(e)) from e

    # Start with full environment args (unfiltered). We will filter late so that
    # any mutations (e.g. isolated build path rewrites) are preserved before
    # applying the per-command allow‑list.
    env_args: dict[str, Any] = {**env_spec.args, "vars": env_spec.vars}

    # Always enforce project-dir to be the real project path initially
    env_args["project-dir"] = str(dbt_project_path)

    # Isolated build logic if gitref provided
    isolated_dbt_project_path: Optional[Path] = None
    if gitref:
        if env_spec.name is None:
            raise ValueError(
                "Cannot run an isolated build without a resolvable environment (no default set?)."
            )

        repo_path = get_repo_path(dbt_project_path)
        full_commit_hash = get_full_commit_hash(repo_path, gitref)
        short_hash = get_short_commit_hash(repo_path, gitref)
        isolated_build_path = repo_path / ".dot" / "build" / short_hash

        worktree_path = isolated_build_path / "worktree"
        commit_file = isolated_build_path / "commit"
        if not commit_file.exists():
            commit_file.parent.mkdir(parents=True, exist_ok=True)
            commit_file.write_text(full_commit_hash)

        create_worktree(repo_path, worktree_path, full_commit_hash)

        # Compute the project path relative to the repo root explicitly to avoid Windows Path.relative_to pitfalls
        rel_project_path = dbt_project_path.resolve().relative_to(repo_path.resolve())
        isolated_dbt_project_path = (worktree_path / rel_project_path).resolve()

        if not isolated_dbt_project_path.exists():
            raise ValueError(
                f"dbt project path does not exist in worktree: {dbt_project_path}"
            )
        if not (isolated_dbt_project_path / "dbt_project.yml").exists():
            raise ValueError(
                f"dbt_project.yml does not exist in worktree: {dbt_project_path / 'dbt_project.yml'}"
            )

        isolated_environment_path = isolated_build_path / "env" / env_spec.name

        write_isolated_profiles_yml(
            dbt_project_path,
            isolated_dbt_project_path,
            isolated_environment_path,
            short_hash,
            env_spec.name,
        )

        # Redirect dbt to isolated directories
        env_args["profiles-dir"] = str(isolated_environment_path)
        env_args["target-path"] = str(isolated_environment_path / "target")
        env_args["log-path"] = str(isolated_environment_path / "logs")
        env_args["project-dir"] = str(isolated_dbt_project_path)

    # Inject deferral flags if a defer_path path was supplied (commit-based immutable baseline)
    if defer_path:
        env_args["defer"] = True
        env_args["favor-state"] = True
        env_args["state"] = str(defer_path)

    dbt_cmd = _dbt_command(dbt_command_name, env_args, passthrough_args)

    logger.debug(
        f"[bold]dbt_project_path:[/] {isolated_dbt_project_path if gitref else dbt_project_path}",
    )
    logger.debug("[bold]Resolved dot Environment Config:[/]")
    logger.debug(json.dumps(env_args, indent=2))

    return dbt_cmd

# ---------------------------------------------------------------------------
# Internal command build
# ---------------------------------------------------------------------------

def _dbt_command(
    dbt_command_name: str,
    environment: dict[str, Any],
    passthrough_args: List[str],
) -> list[str]:
    """
    Build the dbt command list.

    Performs late per-command allow‑list filtering on the provided environment
    (which may contain extra keys added or mutated earlier, e.g. isolated build
    path rewrites) and then converts it to dbt CLI flags. Vars are JSON encoded
    into a single --vars=... argument if present.
    """
    # Late filtering (after any mutations in dbt_command)
    allowed = set(a.lstrip("-") for a in DBT_COMMAND_ARGS.get(dbt_command_name, []))
    environment = {k: v for k, v in environment.items() if k == "vars" or k in allowed}

    dbt_cmd: List[str] = ["dbt", dbt_command_name]

    vars_dict = environment.get("vars", {})
    # exclude vars from normal key->arg generation
    env_no_vars = {k: v for k, v in environment.items() if k != "vars"}

    if isinstance(vars_dict, dict) and len(vars_dict) > 0:
        vars_json = json.dumps(vars_dict)
        dbt_cmd.append(f"--vars={vars_json}")

    for k, v in env_no_vars.items():
        if isinstance(v, bool):
            if v:
                dbt_cmd.append(f"--{k}")
        elif v is not None and v != "":
            dbt_cmd.append(f"--{k}")
            dbt_cmd.append(str(v))

    dbt_cmd += passthrough_args
    return dbt_cmd
