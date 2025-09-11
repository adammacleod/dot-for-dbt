import yaml
import json
import subprocess
from pathlib import Path

from . import logging

logger = logging.get_logger("dot.profiles")

def write_isolated_profiles_yml(
    dbt_project_path: Path,
    isolated_dbt_project_path: Path,
    isolated_environment_path: Path,
    short_hash: str,
    active_environment: str,
) -> None:
    """
    Write a dbt profiles.yml for an isolated schema build.

    Args:
        dbt_project_path (Path): The path to the original dbt project directory.
        isolated_dbt_project_path (Path): The path to the isolated dbt project directory.
        isolated_environment_path (Path): Path where profiles.yml will be written.
        short_hash (str): The short commit hash.
        active_environment (str): The dbt environment/target name to use.
    """

    # TODO: The user may pass a profile name on the command line. We need to source 
    # the profile name from here rather than dbt_project.yml if it is set!
    # 
    #   --profile TEXT   Which existing profile to load. Overrides
    #                    setting in dbt_project.yml.

    # Get the profile name from dbt_project.yml
    dbt_project_yml_path = dbt_project_path / "dbt_project.yml"
    with open(dbt_project_yml_path, "r") as f:
        dbt_project = yaml.safe_load(f)
    profile_name = dbt_project.get("profile")

    if not profile_name:
        raise ValueError(f"Profile name not found in: {dbt_project_yml_path}")

    # We read the profiles.yml from the original dbt project, because this
    # is the actively configured dbt profile for the end user of dot.
    profiles_yml_path = _profiles_yml_path(dbt_project_path, active_environment)
    with open(profiles_yml_path, "r") as f:
        all_profiles = yaml.safe_load(f)

    # Get the profile from profiles.yml
    if profile_name not in all_profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {profiles_yml_path}")
    profile = all_profiles[profile_name]

    # Get the correct output configuration
    if "outputs" not in profile:
        raise ValueError(f"Profile '{profile_name}' does not have an 'outputs' section in {profiles_yml_path}")
    
    if active_environment not in profile["outputs"]:
        raise ValueError(f"Target '{active_environment}' not found in outputs of profile '{profile_name}' within {profiles_yml_path}")

    target = profile["outputs"][active_environment]

    field = "schema"
    if "schema" in target and "dataset" in target:
        raise ValueError("Both 'schema' and 'dataset' are set in the target configuration in profiles.yml. Only one should be set.")
    elif "dataset" in target:
        field = "dataset"

    target[field] = f"{target.get(field, 'dbt')}_{short_hash}"

    new_profiles_yml = {
        profile_name: {
            "target": active_environment,
            "outputs": {
                active_environment: target
            }
        }
    }

    isolated_environment_path.mkdir(parents=True, exist_ok=True)

    with open(isolated_environment_path / "profiles.yml", "w") as f:
        yaml.safe_dump(
            new_profiles_yml,
            f,
            default_flow_style=False
        )

def _profiles_yml_path(
    dbt_project_path: Path,
    active_environment: str
) -> Path:
    """
    Detect the location of profiles.yml using dbt debug output.

    Args:
        dbt_project_path (Path): The path to the dbt project directory.
        active_environment (str): The dbt environment/target name to use.

    Returns:
        Path: The path to the detected profiles.yml file.

    Raises:
        FileNotFoundError: If the profiles.yml location cannot be detected.
    """

    # NOTE (ADR 0002):
    # Configuration for environments & vars is now sourced from:
    #   dot_environments.yml (+ optional dot_environments.user.yml)
    # at the project root. We intentionally DO NOT (yet) load the historical
    # version of configuration from the isolated worktree for `dbt debug`
    # resolution because we want the active developer context (profiles location)
    # rather than historical variance. A future enhancement may optionally allow
    # resolving config from the worktree commit if reproducibility of config
    # definitions (not just code) becomes critical.

    logger.debug("Detecting profiles.yml location with `dbt debug`:")
    from .dot import dbt_command
    dbt_cmd = dbt_command(
        dbt_command_name="debug",
        dbt_project_path=dbt_project_path,
        active_environment=active_environment,
        passthrough_args=[
            "--config-dir",
            "--log-format", "json",
            "--no-quiet",
            "--log-level", "info"
        ],
        log_level=logging.DEBUG,
    )

    result = subprocess.run(
        dbt_cmd,
        check=True,
        capture_output=True,
        text=True
    )

    logger.debug(f"[bold]dbt debug output:[/]\n{result.stdout}")

    profiles_dir = None
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = obj.get("data")
        if isinstance(data, dict) and "profiles_dir" in data:
            profiles_dir = data["profiles_dir"]
            break

    if not profiles_dir:
        raise FileNotFoundError("Could not parse profiles_dir from dbt debug json output.")

    path = Path(profiles_dir) / "profiles.yml"

    logger.info(f"[bold]Detected profiles.yml location:[/] {path}")

    if path.exists():
        return path

    raise FileNotFoundError(f"profiles.yml not found at detected location: {path}")
