import yaml
import json

from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from . import logging
from .logging import get_logger
from .profiles import write_isolated_profiles_yml
from .git import (
    create_worktree,
    get_repo_path,
    get_full_commit_hash,
    get_short_commit_hash,
)

logger = get_logger("dot.dot")

# Common dbt CLI arguments used across subcommands.
COMMON_DBT_ARGS = [
    "--vars",
    "--target",
    "--profiles-dir",
    "--project-dir",
    "--target-path",
    "--log-path",
]

# Allowed dbt CLI arguments for each subcommand, based on dbt documentation.
DBT_COMMAND_ARGS = {
    "build": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--resource-type",
        "--defer",
    ],
    "clean": [
        *COMMON_DBT_ARGS,
    ],
    "clone": [
        *COMMON_DBT_ARGS,
    ],
    "compile": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--inline",
    ],
    "debug": [
        *COMMON_DBT_ARGS,
    ],
    "deps": [
        *COMMON_DBT_ARGS,
    ],
    "docs": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
    ],
    "init": [
        *COMMON_DBT_ARGS,
    ],
    "list": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--resource-type",
    ],
    "parse": [
        *COMMON_DBT_ARGS,
    ],
    "retry": [
        *COMMON_DBT_ARGS,
    ],
    "run": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--defer",
    ],
    "run-operation": [
        *COMMON_DBT_ARGS,
        "--args",
    ],
    "seed": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
    ],
    "show": [
        *COMMON_DBT_ARGS,
        "--select",
    ],
    "snapshot": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
    ],
    "source": [
        *COMMON_DBT_ARGS,
    ],
    "test": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--defer",
    ],
}


def dbt_command(
    dbt_command_name: str,
    dbt_project_path: Path,
    vars_yml_path: Path,
    active_environment: Optional[str],
    passthrough_args: Optional[list[str]] = None,
    gitref: Optional[str] = None,
    log_level: int = logging.INFO,
) -> list[str]:
    """
    Construct a dbt CLI command as a list of arguments.

    If a gitref is passed then this command will checkout a clean worktree of that
    commit and return the dbt_project_path for the dbt project within the new
    worktree.

    It will also make a copy of your main repositories profiles.yml, and update
    it's configuration to write into an isolated schema named
    <schema>_<short_hash>.

    Args:
        dbt_command_name (str): The dbt subcommand to run (e.g., 'run', 'test').
        dbt_project_path (Path): Path to the dbt project root.
        vars_yml_path (Path): Path to the vars.yml configuration file.
        active_environment (Optional[str]): Name of the environment to use from vars.yml.
        passthrough_args (Optional[List[str]]): Additional arguments to pass through to dbt.
        gitref (Optional[str]): Git ref or commit hash for isolated build.

    Returns:
        List[str]: The dbt command
    """
    passthrough_args = passthrough_args if passthrough_args else []

    if dbt_project_path is None:
        raise ValueError("dbt_project_path must be provided")

    if not (dbt_project_path / "dbt_project.yml").exists():
        raise ValueError(f"dbt_project.yml not found in: {dbt_project_path}")

    # config_environment is the 'environment' dict, which may contain 'all', 'default', and named environments
    config_vars, config_environment = _load_vars_yml(vars_yml_path)
    merged_environment = _resolve_environment(config_environment, active_environment)

    # Force dbt to build the project within our project path, regardless of cwd.
    merged_environment["project-dir"] = str(dbt_project_path)

    # Isolated build logic if gitref is provided
    if gitref:
        repo_path = get_repo_path(dbt_project_path)
        full_commit_hash = get_full_commit_hash(repo_path, gitref)
        short_hash = get_short_commit_hash(repo_path, gitref)
        isolated_build_path = repo_path / ".dot" / "build" / short_hash

        worktree_path = isolated_build_path / "worktree"
        # Write the full hash to commit file (idempotent)
        commit_file = isolated_build_path / "commit"
        if not commit_file.exists():
            commit_file.parent.mkdir(parents=True, exist_ok=True)
            commit_file.write_text(full_commit_hash)

        create_worktree(repo_path, worktree_path, full_commit_hash)

        # Calculate the relative path of the dbt project inside of the repository,
        # and then create isolated_dbt_project_path to point to this path inside of the new worktree.
        isolated_dbt_project_path = (
            worktree_path / Path.relative_to(dbt_project_path, repo_path)
        ).resolve()

        if not isolated_dbt_project_path.exists():
            raise ValueError(
                f"dbt project path does not exist in worktree: {dbt_project_path}"
            )

        if not (isolated_dbt_project_path / "dbt_project.yml").exists():
            raise ValueError(
                f"dbt_project.yml does not exist in worktree: {dbt_project_path / 'dbt_project.yml'}"
            )

        # We create a folder inside of the build path for each environment which
        # can build against this project. The isolated_environment_path contains
        # a profiles.yml for environment and commit_hash, and also the target
        # folder which contains dbt build artifacts.
        isolated_environment_path = isolated_build_path / "env" / active_environment

        write_isolated_profiles_yml(
            dbt_project_path,
            isolated_dbt_project_path,
            isolated_environment_path,
            short_hash,
            active_environment,
        )

        # Point dbt towards the profiles.yml in our isolated_environment_path,
        # the target directory for build artifacts, and the isolated project
        # directory for running dbt.
        merged_environment["profiles-dir"] = str(isolated_environment_path)
        merged_environment["target-path"] = str(isolated_environment_path / "target")
        merged_environment["project-dir"] = str(isolated_dbt_project_path)
        merged_environment["log-path"] = str(isolated_environment_path / "logs")

    dbt_cmd = _dbt_command(dbt_command_name, merged_environment, passthrough_args)

    logger.log(
        log_level,
        f"[bold]dbt_project_path:[/] {isolated_dbt_project_path if gitref else dbt_project_path}",
    )
    logger.debug("dbt Command Environment:")
    logger.debug(json.dumps(merged_environment, indent=2))
    logger.log(
        log_level, f"[bold]dbt command:[/] [green]{' '.join(dbt_cmd)}[/]"
    )

    return dbt_cmd


def _load_vars_yml(path: Path) -> Tuple[dict[str, Any], dict[str, Any]]:
    """
    Load the vars.yml file from the specified path.

    Args:
        path (Path): Path to the vars.yml file.

    Returns:
        Tuple[Dict[str, Any], Dict[str, Any]]: A tuple containing the 'vars' and 'environment' dictionaries.

    Raises:
        ValueError: If the path is None.
        FileNotFoundError: If the file does not exist.
        RuntimeError: If the file cannot be read or parsed.
    """
    if path is None:
        raise ValueError("A path to vars.yml must be provided.")

    if not path.exists():
        raise FileNotFoundError(f"vars.yml not found at: {path}")

    config: Dict[str, Any] = {}

    try:
        with open(path, "r") as f:
            config = yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError(f"Error reading vars.yml: {e}")

    config_vars = config.get("vars", {})
    config_environment = config.get("environment", {})

    return config_vars, config_environment


def _resolve_environment(
    config_environment: dict[str, Any], active_environment: Optional[str] = None
) -> dict[str, Any]:
    """
    Resolve and merge the dbt environment configuration, returning the environment configuration for
    the active_environment.

    When specifying environments in vars.yml, there is a special environment called `all` which contains
    variables and settings that are applicable to all environments. This allows for a base set of
    configurations to be defined once and reused across different environments.

    We merge the 'all' environment with the selected environment (by name), or the default if not specified.
    We will prioritize the selected environment's variables over the 'all' environment.

    Args:
        config_environment (Dict[str, Any]): The 'environment' dictionary from vars.yml.
        active_environment (Optional[str]): The name of the environment to use. If None, uses the default.

    Returns:
        Dict[str, Any]: The merged environment dictionary for the active_environment only.

    Raises:
        ValueError: If the specified environment is not found.
    """

    default_environment_name: Optional[str] = config_environment.get("default")

    if active_environment is None:
        active_environment = default_environment_name

    if active_environment and (
        not config_environment or active_environment not in config_environment
    ):
        raise ValueError(f"Environment '{active_environment}' not found in vars.yml.")

    merged_environment: Dict[str, Any] = {}
    environment_all = config_environment.get("all", {})
    environment_selected = config_environment.get(active_environment, {})

    merged_environment.update(environment_all)
    merged_environment.update(environment_selected)

    return merged_environment


def _dbt_command(
    dbt_command_name: str,
    environment: dict[str, Any],
    passthrough_args: list[str],
) -> list[str]:
    """
    Build the dbt command list from the provided environment and arguments.

    Args:
        dbt_command_name (str): The dbt subcommand to run.
        environment (Dict[str, Any]): The merged environment dictionary containing dbt options and variables.
        passthrough_args (List[str]): Additional arguments to append to the dbt command.

    Returns:
        List[str]: The complete dbt command as a list of arguments.
    """
    # Filter environment to only allowed args for this subcommand
    filtered_environment = _filter_allowed_args(dbt_command_name, environment)

    dbt_cmd: List[str] = ["dbt", dbt_command_name]

    vars_dict = filtered_environment.get("vars", {})
    filtered_environment.pop("vars", None)

    if len(vars_dict) > 0:
        vars_json = json.dumps(vars_dict)
        dbt_cmd.append(f"--vars={vars_json}")

    for k, v in filtered_environment.items():
        if isinstance(v, bool):
            if v:
                dbt_cmd.append(f"--{k}")
        elif v is not None and v != "":
            dbt_cmd.append(f"--{k}")
            dbt_cmd.append(str(v))

    dbt_cmd += passthrough_args

    return dbt_cmd


def _filter_allowed_args(
    dbt_command_name: str, environment: dict[str, Any]
) -> dict[str, Any]:
    """
    Filter the environment dictionary to only include allowed arguments for the given dbt subcommand.

    This function is used to ensure that only arguments explicitly allowed for a specific dbt subcommand
    (as defined in DBT_COMMAND_ARGS) are included in the command environment generated by project logic or
    vars.yml. This prevents accidental or unsupported arguments from being injected into the dbt CLI
    invocation by project configuration, while still allowing end users to pass any arguments directly
    via passthrough_args.

    Args:
        dbt_command_name (str): The dbt subcommand to run (e.g., 'run', 'build', 'test').
        environment (Dict[str, Any]): The merged environment dictionary containing dbt options and variables
            generated from project logic or vars.yml.

    Returns:
        Dict[str, Any]: A new dictionary containing only the allowed arguments for the specified
            dbt subcommand, plus the 'vars' key if present.

    Usage:
        This function is called internally by _dbt_command before constructing the final dbt CLI
        command. It does not affect passthrough_args, which are always passed through unfiltered.

    Example:
        filtered_environment = _filter_allowed_args("run", {"select": "my_model", "foo": "bar", "vars": {...}})
        # Result: {"select": "my_model", "vars": {...}}
    """
    allowed = set(a.lstrip("-") for a in DBT_COMMAND_ARGS.get(dbt_command_name, []))
    filtered = {}
    for k, v in environment.items():
        if k in allowed:
            filtered[k] = v
    return filtered
