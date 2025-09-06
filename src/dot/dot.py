import yaml
import json

from pathlib import Path
from typing import Dict, Any, Optional, List

from . import logging
from .logging import get_logger
from .profiles import write_isolated_profiles_yml
from .git import create_worktree, get_repo_path, get_commit_hash_from_gitref

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
    active_context: Optional[str],
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
    it's configuration to write into an isolated schema labelled 
    <schema>_<commithash>.

    Args:
        dbt_command_name (str): The dbt subcommand to run (e.g., 'run', 'test').
        dbt_project_path (Path): Path to the dbt project root.
        vars_yml_path (Path): Path to the vars.yml configuration file.
        active_context (Optional[str]): Name of the context to use from vars.yml.
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

    # config_context is the 'context' dict, which may contain 'all', 'default', and named contexts
    config_vars, config_context = _load_vars_yml(vars_yml_path)
    merged_context = _resolve_context(config_context, active_context)
    
    # Force dbt to build the project within our project path, regardless of cwd.
    merged_context['project-dir'] = str(dbt_project_path)

    # Isolated build logic if gitref is provided
    if gitref:
        repo_path = get_repo_path(dbt_project_path)
        commit_hash = get_commit_hash_from_gitref(repo_path, gitref)
        isolated_build_path = repo_path / '.dot' / 'isolated_builds' / commit_hash
        
        worktree_path = isolated_build_path / 'worktree'

        create_worktree(
            repo_path,
            worktree_path,
            commit_hash
        )

        # Calculate the relative path of the dbt project inside of the repository,
        # and then create isolated_dbt_project_path to point to this path inside of the new worktree.
        isolated_dbt_project_path = (
            worktree_path / Path.relative_to(dbt_project_path, repo_path)
        ).resolve()
        
        if not isolated_dbt_project_path.exists():
            raise ValueError(f"dbt project path does not exist in worktree: {dbt_project_path}")

        if not (isolated_dbt_project_path / "dbt_project.yml").exists():
            raise ValueError(f"dbt_project.yml does not exist in worktree: {dbt_project_path / 'dbt_project.yml'}")

        # We create a folder inside of the build path for each context which
        # can build against this project. The isolated_context_path contains
        # a profiles.yml for context and commit_hash, and also the target
        # folder which contains dbt build artifacts.
        isolated_context_path = isolated_build_path / active_context

        # By this point there are two dbt projects, the one we are operating on,
        # and the isolated one which we have checked out in our worktree.
        # We will resolve profiles.yml by operating on the main one that we are
        # working with. After resolving the profiles.yml configuration, we will
        # write it to the isolated profiles directory.
        write_isolated_profiles_yml(
            dbt_project_path,
            isolated_dbt_project_path,
            isolated_context_path,
            commit_hash,
            active_context
        )

        # Point dbt towards the profiles.yml in our isolated_context_path,
        # the target directory for build artifacts, and the isolated project
        # directory for running dbt.
        merged_context['profiles-dir'] = str(isolated_context_path)
        merged_context['target-path'] = str(isolated_context_path / 'target')
        merged_context['project-dir'] = str(isolated_dbt_project_path)
        merged_context['log-path'] = str(isolated_context_path / 'logs')

    dbt_command = _dbt_command(
        dbt_command_name, 
        merged_context, 
        passthrough_args
    )

    logger.log(
        log_level, 
        f"[bold]dbt_project_path:[/] {isolated_dbt_project_path if gitref else dbt_project_path}"
    )
    logger.debug("dbt Command Context:")
    logger.debug(json.dumps(merged_context, indent=2))
    logger.log(
        log_level,
        f"[bold]dbt command:[/] [green]{' '.join(dbt_command)}[/]"
    )

    return dbt_command

def _load_vars_yml(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Load the vars.yml file from the specified path.

    Args:
        path (Path): Path to the vars.yml file.

    Returns:
        Tuple[Dict[str, Any], Dict[str, Any]]: A tuple containing the 'vars' and 'context' dictionaries.

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
            config = yaml.safe_load(f)
    except Exception as e:
        raise RuntimeError(f"Error reading vars.yml: {e}")
    
    config_vars = config.get("vars", {})
    config_context = config.get("context", {})
    
    return config_vars, config_context


def _resolve_context(
    config_context: dict[str, Any], 
    active_context: Optional[str] = None
) -> dict[str, Any]:
    """
    Resolve and merge the dbt context configuration, returning the context configuration for
    the active_context.

    When specifying contexts in vars.yml, there is a special context called `all` which contains
    variables and settings that are applicable to all contexts. This allows for a base set of
    configurations to be defined once and reused across different contexts.

    We merge the 'all' context with the selected context (by name), or the default if not specified.
    We will prioritize the selected context's variables over the 'all' context.

    Args:
        config_context (Dict[str, Any]): The 'context' dictionary from vars.yml.
        active_context (Optional[str]): The name of the context to use. If None, uses the default.

    Returns:
        Dict[str, Any]: The merged context dictionary for the active_context only.

    Raises:
        ValueError: If the specified context is not found.
    """

    default_context_name: Optional[str] = config_context.get("default")

    if active_context is None:
        active_context = default_context_name

    if active_context and (not config_context or active_context not in config_context):
        raise ValueError(f"Context '{active_context}' not found in vars.yml.")
    
    merged_context: Dict[str, Any] = {}
    context_all = config_context.get("all", {})
    context_selected = config_context.get(active_context, {})

    merged_context.update(context_all)
    merged_context.update(context_selected)

    return merged_context


def _dbt_command(
    dbt_command_name: str,
    context: dict[str, Any],
    passthrough_args: list[str],
) -> list[str]:
    """
    Build the dbt command list from the provided context and arguments.

    Args:
        dbt_command_name (str): The dbt subcommand to run.
        context (Dict[str, Any]): The merged context dictionary containing dbt options and variables.
        passthrough_args (List[str]): Additional arguments to append to the dbt command.

    Returns:
        List[str]: The complete dbt command as a list of arguments.
    """
    # Filter context to only allowed args for this subcommand
    filtered_context = _filter_allowed_args(dbt_command_name, context)

    dbt_command: List[str] = ['dbt', dbt_command_name]

    vars = filtered_context.get("vars", {})
    filtered_context.pop("vars", None)

    if len(vars) > 0:
        vars_json = json.dumps(vars)
        dbt_command.append(f'--vars={vars_json}')

    for k, v in filtered_context.items():
        if isinstance(v, bool):
            if v:
                dbt_command.append(f"--{k}")
        elif v is not None and v != "":
            dbt_command.append(f"--{k}")
            dbt_command.append(str(v))

    dbt_command += passthrough_args

    return dbt_command


def _filter_allowed_args(dbt_command_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """
    Filter the context dictionary to only include allowed arguments for the given dbt subcommand.

    This function is used to ensure that only arguments explicitly allowed for a specific dbt subcommand
    (as defined in DBT_COMMAND_ARGS) are included in the command context generated by project logic or
    vars.yml. This prevents accidental or unsupported arguments from being injected into the dbt CLI
    invocation by project configuration, while still allowing end users to pass any arguments directly
    via passthrough_args.

    Args:
        dbt_command_name (str): The dbt subcommand to run (e.g., 'run', 'build', 'test').
        context (Dict[str, Any]): The merged context dictionary containing dbt options and variables
            generated from project logic or vars.yml.

    Returns:
        Dict[str, Any]: A new dictionary containing only the allowed arguments for the specified
            dbt subcommand, plus the 'vars' key if present.

    Usage:
        This function is called internally by _dbt_command before constructing the final dbt CLI
        command. It does not affect passthrough_args, which are always passed through unfiltered.

    Example:
        filtered_context = _filter_allowed_args("run", {"select": "my_model", "foo": "bar", "vars": {...}})
        # Result: {"select": "my_model", "vars": {...}}
    """
    allowed = set(a.lstrip('-') for a in DBT_COMMAND_ARGS.get(dbt_command_name, []))
    filtered = {}
    for k, v in context.items():
        if k in allowed:
            filtered[k] = v
    return filtered
