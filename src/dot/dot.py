import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

# Allowed dbt CLI arguments for each subcommand, based on dbt documentation.
DBT_COMMAND_ARGS = {
    "build": ["--select", "--exclude", "--selector", "--resource-type", "--defer", "--vars", "--target"],
    "clean": ["--vars", "--target"],
    "clone": ["--vars", "--target"],
    "compile": ["--select", "--exclude", "--selector", "--inline", "--vars", "--target"],
    "debug": ["--vars", "--target"],
    "deps": ["--vars", "--target"],
    "docs": ["--select", "--exclude", "--selector", "--vars", "--target"],  # docs generate
    "init": ["--vars", "--target"],
    "list": ["--select", "--exclude", "--selector", "--resource-type", "--vars", "--target"],
    "parse": ["--vars", "--target"],
    "retry": ["--vars", "--target"],
    "run": ["--select", "--exclude", "--selector", "--defer", "--vars", "--target"],
    "run-operation": ["--args", "--vars", "--target"],
    "seed": ["--select", "--exclude", "--selector", "--vars", "--target"],
    "show": ["--select", "--vars", "--target"],
    "snapshot": ["--select", "--exclude", "--selector", "--vars", "--target"],
    "source": ["--vars", "--target"],
    "test": ["--select", "--exclude", "--selector", "--defer", "--vars", "--target"],
}


def dbt_command(
    dbt_command_name: str,
    vars_yml_path: Path,
    active_context: Optional[str],
    passthrough_args: Optional[List[str]] = None,
) -> List[str]:
    """
    Construct a dbt CLI command as a list of arguments.

    Args:
        dbt_command_name (str): The dbt subcommand to run (e.g., 'run', 'test').
        vars_yml_path (Path): Path to the vars.yml configuration file.
        active_context (Optional[str]): Name of the context to use from vars.yml.
        passthrough_args (Optional[List[str]]): Additional arguments to pass through to dbt.

    Returns:
        List[str]: The complete dbt command as a list of arguments.
    """
    # config_context is the 'context' dict, which may contain 'all', 'default', and named contexts
    config_vars, config_context = _load_vars_yml(vars_yml_path)
    merged_context = _resolve_context(config_context, active_context)

    return _dbt_command(
        dbt_command_name, 
        merged_context, 
        passthrough_args if passthrough_args else []
    )


def _load_vars_yml(path: Path) -> Tuple[Dict[str, Any], Dict[str, Any]]:
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
    config_context: Dict[str, Any], 
    active_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Resolve and merge the dbt context configuration.

    When specifying contexts in vars.yml, there is a special context called `all` which contains
    variables and settings that are applicable to all contexts. This allows for a base set of
    configurations to be defined once and reused across different contexts.

    We merge the 'all' context with the selected context (by name), or the default if not specified.
    We will prioritize the selected context's variables over the 'all' context.

    Args:
        config_context (Dict[str, Any]): The 'context' dictionary from vars.yml.
        active_context (Optional[str]): The name of the context to use. If None, uses the default.

    Returns:
        Dict[str, Any]: The merged context dictionary.

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
    context: Dict[str, Any],
    passthrough_args: List[str],
) -> List[str]:
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


def _filter_allowed_args(dbt_command_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
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
