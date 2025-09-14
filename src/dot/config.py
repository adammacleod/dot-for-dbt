from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from .logging import get_logger

logger = get_logger("dot.config")

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ConfigError(Exception):
    """Raised for any configuration loading / validation problems."""

# ---------------------------------------------------------------------------
# Dataclasses representing the structured configuration
# ---------------------------------------------------------------------------

@dataclass
class DotVariableSpec:
    description: Optional[str] = None
    values: Optional[list[Any]] = None
    strict: bool = False
    required: bool = False

@dataclass
class DotEnvironmentSpec:
    name: Optional[str]
    args: Dict[str, Any] = field(default_factory=dict)   # dbt CLI args (excluding vars)
    vars: Dict[str, Any] = field(default_factory=dict)   # resolved variable values for this environment

@dataclass
class DotConfig:
    variables: Dict[str, DotVariableSpec]
    default_environment: Optional[str]
    project_root: Path
    # Original (unmerged) sections retained to compute fine‑grained precedence
    # Precedence order for vars & args (lowest -> highest):
    #   project_all < project_env < user_all < user_env
    project_environments: Dict[str, Any] = field(default_factory=dict)
    user_environments: Dict[str, Any] = field(default_factory=dict)

# ---------------------------------------------------------------------------
# dbt command argument allow‑list
# ---------------------------------------------------------------------------

COMMON_DBT_ARGS = [
    "--vars",
    "--target",
    "--profiles-dir",
    "--project-dir",
    "--log-path",
]

DBT_COMMAND_ARGS = {
    "build": [
        *COMMON_DBT_ARGS,
        "--target-path",
        "--select",
        "--exclude",
        "--selector",
        "--resource-type",
        "--defer",
    ],
    "clean": [*COMMON_DBT_ARGS],
    "clone": [*COMMON_DBT_ARGS],
    "compile": [
        *COMMON_DBT_ARGS,
        "--target-path",
        "--select",
        "--exclude",
        "--selector",
        "--inline",
    ],
    "debug": [*COMMON_DBT_ARGS],
    "deps": [*COMMON_DBT_ARGS],
    "docs": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
    ],
    "init": [*COMMON_DBT_ARGS],
    "list": [
        *COMMON_DBT_ARGS,
        "--select",
        "--exclude",
        "--selector",
        "--resource-type",
    ],
    "parse": [*COMMON_DBT_ARGS],
    "retry": [*COMMON_DBT_ARGS],
    "run": [
        *COMMON_DBT_ARGS,
        "--target-path",
        "--select",
        "--exclude",
        "--selector",
        "--defer",
    ],
    "run-operation": [
        *COMMON_DBT_ARGS,
        "--target-path",
        "--args",
    ],
    "seed": [
        *COMMON_DBT_ARGS,
        "--target-path",
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
        "--target-path",
        "--select",
        "--exclude",
        "--selector",
    ],
    "source": [*COMMON_DBT_ARGS],
    "test": [
        *COMMON_DBT_ARGS,
        "--target-path",
        "--select",
        "--exclude",
        "--selector",
        "--defer",
    ],
}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_CONFIG_FILENAME = "dot_environments.yml"
USER_CONFIG_FILENAME = "dot_environments.user.yml"
PROJECT_VARIABLES_FILENAME = "dot_vars.yml"

# This set avoids redundant logging of config load attempts
_logged_config_roots: set[str] = set()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_config(project_root: Path) -> DotConfig:
    """
    Load and merge configuration:
      - Variable specifications from dot_vars.yml (if present)
      - Environment definitions from dot_environments.yml (+ user overrides)
    The project remains functional if none of these files exist (empty config).
    """
    project_env_file = project_root / PROJECT_CONFIG_FILENAME
    user_env_file = project_root / USER_CONFIG_FILENAME
    variables_file = project_root / PROJECT_VARIABLES_FILENAME

    root_key = str(project_root.resolve())
    if root_key not in _logged_config_roots:
        _logged_config_roots.add(root_key)
        logger.debug(f"[blue]⚙️  Loading dot configuration for {project_root}[/]")
        if project_env_file.exists():
            logger.debug(f"Found {PROJECT_CONFIG_FILENAME} at {project_env_file}")
        else:
            logger.debug(f"[yellow]Couldn't find {PROJECT_CONFIG_FILENAME}[/] at {project_env_file}")
        if user_env_file.exists():
            logger.debug(f"Found {USER_CONFIG_FILENAME} at {user_env_file}")
        else:
            logger.debug(f"[yellow]Couldn't find {USER_CONFIG_FILENAME}[/] at {user_env_file}")
        if variables_file.exists():
            logger.debug(f"Found {PROJECT_VARIABLES_FILENAME} at {variables_file}")
        else:
            logger.debug(f"[yellow]Couldn't find {PROJECT_VARIABLES_FILENAME}[/] at {variables_file}")

    variables = _read_variables_specs(variables_file)

    project_env_root = _read_yaml_optional(project_env_file)
    user_env_root = _read_yaml_optional(user_env_file)

    # Reject legacy root-level vars usage in environment files (full switch)
    if "vars" in project_env_root:
        raise ConfigError(
            f"Root-level 'vars' found in {PROJECT_CONFIG_FILENAME}. Variable specifications now belong in {PROJECT_VARIABLES_FILENAME}."
        )
    if "vars" in user_env_root:
        raise ConfigError(
            f"Root-level 'vars' found in {USER_CONFIG_FILENAME}. Variable specifications now belong in {PROJECT_VARIABLES_FILENAME}."
        )

    base_env_section = project_env_root.get("environment", {}) or {}
    override_env_section = user_env_root.get("environment", {}) or {}

    merged_env_section = _merge_environment(base_env_section, override_env_section)
    default_env = merged_env_section.get("default")

    _validate_structure(merged_env_section)

    return DotConfig(
        variables=variables,
        default_environment=default_env,
        project_root=project_root,
        project_environments=base_env_section,
        user_environments=override_env_section,
    )

def resolve_environment(cfg: DotConfig, name: Optional[str]) -> DotEnvironmentSpec:
    """
    Resolve the effective environment by name (or default). Returns merged args and vars.

    Precedence strategy (lowest -> highest):
      project_all < project_env < user_all < user_env
    This allows a user-level 'all' override to trump a project-specific value,
    which is required for flexible local experimentation (see tests).
    Variable validation (required / strict) only applies to declared specs.
    """
    if name is None:
        name = cfg.default_environment

    if name is None:
        return DotEnvironmentSpec(name=None, args={}, vars={})

    project_envs = cfg.project_environments or {}
    user_envs = cfg.user_environments or {}

    available_envs = set(project_envs.keys()) | set(user_envs.keys())
    available_envs.discard("all")

    if name not in available_envs:
        raise ConfigError(
            f"Environment '{name}' not found in configuration. "
            f"Defined environments: {', '.join(sorted(available_envs)) or 'none'}"
        )

    project_all = project_envs.get("all", {}) if isinstance(project_envs, dict) else {}
    project_specific = project_envs.get(name, {}) if isinstance(project_envs, dict) else {}
    user_all = user_envs.get("all", {}) if isinstance(user_envs, dict) else {}
    user_specific = user_envs.get(name, {}) if isinstance(user_envs, dict) else {}

    def extract_vars(section: Any) -> Dict[str, Any]:
        if isinstance(section, dict):
            v = section.get("vars")
            return v if isinstance(v, dict) else {}
        return {}

    project_all_vars = extract_vars(project_all)
    project_specific_vars = extract_vars(project_specific)
    user_all_vars = extract_vars(user_all)
    user_specific_vars = extract_vars(user_specific)

    merged_vars: Dict[str, Any] = {}
    # Apply precedence order
    for layer in (project_all_vars, project_specific_vars, user_all_vars, user_specific_vars):
        merged_vars.update(layer)

    # Args (non-vars keys) follow identical precedence
    def apply_args(src: Any, dest: Dict[str, Any]):
        if not isinstance(src, dict):
            return
        for k, v in src.items():
            if k == "vars":
                continue
            dest[k] = v

    merged_args: Dict[str, Any] = {}
    for layer in (project_all, project_specific, user_all, user_specific):
        apply_args(layer, merged_args)

    _validate_variable_assignments(cfg.variables, name, merged_vars)

    return DotEnvironmentSpec(name=name, args=merged_args, vars=merged_vars)

def dbt_cli_args(dbt_command_name: str, env_spec: DotEnvironmentSpec) -> Dict[str, Any]:
    """
    Return a dictionary of allowed dbt CLI arguments for the given command,
    including vars (unfiltered).
    """
    allowed = set(a.lstrip("-") for a in DBT_COMMAND_ARGS.get(dbt_command_name, []))
    filtered: Dict[str, Any] = {}

    for k, v in env_spec.args.items():
        if k in allowed:
            filtered[k] = v

    filtered["vars"] = env_spec.vars
    return filtered

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_yaml_optional(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ConfigError(f"Top-level YAML in {path} must be a mapping.")
            return data
    except Exception as e:
        raise ConfigError(f"Failed to read {path}: {e}") from e

def _read_variables_specs(path: Path) -> Dict[str, DotVariableSpec]:
    if not path.exists():
        return {}
    raw = _read_yaml_optional(path)
    if "vars" not in raw:
        # Empty spec file allowed
        return {}
    vars_block = raw["vars"]
    if not isinstance(vars_block, dict):
        raise ConfigError(f"'vars' in {PROJECT_VARIABLES_FILENAME} must be a mapping.")
    variables: Dict[str, DotVariableSpec] = {}
    for name, spec in vars_block.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"Variable spec for '{name}' must be a mapping.")
        variables[name] = DotVariableSpec(
            description=spec.get("description"),
            values=spec.get("values"),
            strict=bool(spec.get("strict", False)),
            required=bool(spec.get("required", False)),
        )
    return variables

def _merge_environment(base_env: dict, override_env: dict) -> dict:
    """
    Merge environment section with shallow semantics except for nested
    'vars' dictionaries which are deep‑merged so that overrides can
    add or change individual variable values without discarding
    previously defined ones.
    """
    merged: dict = {}
    merged.update(base_env)

    def merge_env_mapping(existing: dict, incoming: dict) -> dict:
        out = {}
        out.update(existing)
        out.update(incoming)
        if isinstance(existing.get("vars"), dict) and isinstance(incoming.get("vars"), dict):
            nv = existing["vars"].copy()
            nv.update(incoming["vars"])
            out["vars"] = nv
        return out

    for k, v in override_env.items():
        if isinstance(v, dict) and k in ("default", "all"):
            existing = merged.get(k, {}) or {}
            merged[k] = merge_env_mapping(existing if isinstance(existing, dict) else {}, v)
        elif isinstance(v, dict) and k not in ("default", "all"):
            existing_env = merged.get(k, {}) or {}
            merged[k] = merge_env_mapping(existing_env if isinstance(existing_env, dict) else {}, v)
        else:
            merged[k] = v
    return merged

def _validate_structure(env_section: Dict[str, Any]) -> None:
    default_name = env_section.get("default")
    if default_name and default_name not in env_section:
        raise ConfigError(f"default environment '{default_name}' not defined.")

    for env_name, body in env_section.items():
        if env_name in ("default",):
            continue
        if not isinstance(body, dict):
            raise ConfigError(f"Environment '{env_name}' must be a mapping.")
        if "vars" in body and not isinstance(body["vars"], dict):
            raise ConfigError(f"Environment '{env_name}' vars must be a mapping.")

    if "all" in env_section and not isinstance(env_section["all"], dict):
        raise ConfigError("environment.all must be a mapping.")
    if "all" in env_section and "vars" in env_section["all"]:
        if not isinstance(env_section["all"]["vars"], dict):
            raise ConfigError("environment.all.vars must be a mapping.")

def _validate_variable_assignments(variable_specs: Dict[str, DotVariableSpec], env_name: str, merged_vars: Dict[str, Any]) -> None:
    for var_name, spec in variable_specs.items():
        if spec.required and var_name not in merged_vars:
            raise ConfigError(f"Required variable '{var_name}' is not set for environment '{env_name}'.")
        if spec.strict and var_name in merged_vars:
            allowed = spec.values or []
            if merged_vars[var_name] not in allowed:
                raise ConfigError(
                    f"Variable '{var_name}' has invalid value '{merged_vars[var_name]}' "
                    f"for environment '{env_name}'. Allowed: {allowed}"
                )
