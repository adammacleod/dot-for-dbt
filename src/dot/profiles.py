import yaml
import subprocess
from pathlib import Path

from . import dot, logging
from .logging import get_logger

logger = get_logger("dot.dot")


def write_isolated_profiles_yml(
    dbt_project_path: Path,
    isolated_dbt_project_path: Path,
    isolated_profile_path: Path,
    short_hash: str,
    active_context: str,
) -> None:
    """
    Write a dbt profiles.yml for an isolated schema build.

    Args:
        dbt_project_path (Path): The path to the original dbt project directory.
        isolated_dbt_project_path (Path): The path to the isolated dbt project directory.
        isolated_profile_path (Path): Path where profiles.yml will be written.
        short_hash (str): The short commit hash.
        active_context (str): The dbt context/target name to use.
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
    profiles_yml_path = _profiles_yml_path(dbt_project_path, active_context)
    with open(profiles_yml_path, "r") as f:
        all_profiles = yaml.safe_load(f)

    # Get the profile from profiles.yml
    if profile_name not in all_profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {profiles_yml_path}")
    profile = all_profiles[profile_name]

    # Get the correct output configuration
    if not "outputs" in profile:
        raise ValueError(f"Profile '{profile_name}' does not have an 'outputs' section in {profiles_yml_path}")
    
    if not active_context in profile["outputs"]:
        raise ValueError(f"Target '{active_context}' not found in outputs of profile '{profile_name}' within {profiles_yml_path}")

    target = profile["outputs"][active_context]
    target["schema"] = f"{target.get('schema', 'dbt')}_{short_hash}"

    new_profiles_yml = {
        profile_name: {
            'target': active_context,
            'outputs': {
                active_context: target
            }
        }
    }

    isolated_profile_path.mkdir(parents=True, exist_ok=True)

    with open(isolated_profile_path / "profiles.yml", "w") as f:
        yaml.safe_dump(
            new_profiles_yml, 
            f, 
            default_flow_style=False
        )


def _profiles_yml_path(
    dbt_project_path: Path,
    active_context: str
) -> Path:
    """
    Detect the location of profiles.yml using dbt debug output.

    Args:
        dbt_project_path (Path): The path to the dbt project directory.
        active_context (str): The dbt context/target name to use.

    Returns:
        Path: The path to the detected profiles.yml file.

    Raises:
        FileNotFoundError: If the profiles.yml location cannot be detected.
    """

    # TODO: Decide if we should use vars.yml from the current dbt project, 
    # or the isolated build environment. 
    # I was thinking to take this from the worktree path, although I'm not
    # totally sure. There's reasons for going both ways.
    #
    # main dbt project path: because we are trying to resolve the users
    # current configuration for profiles.yml, and this is probably the most
    # accurate way to do that.
    # 
    # Worktree path: because it sets the defaults for any variables
    # AS AT when that commit was made. This might make more sense once we
    # stabalise vars.yml, and introduce something like user_vars.yml. With
    # the precedence for building the project to go:
    # command line args > user_vars.yml > vars.yml > dbt_project.yml.

    # Use dot.dbt_command to run dbt debug and capture output
    logger.debug("Detecting profiles.yml location with `dbt debug`:")
    dbt_command = dot.dbt_command(
        dbt_command_name="debug",
        dbt_project_path=dbt_project_path,
        vars_yml_path=dbt_project_path / "vars.yml",
        active_context=active_context,
        passthrough_args=['--config-dir'],
        log_level=logging.DEBUG,
    )

    result = subprocess.run(
        dbt_command,
        check=True,
        capture_output=True,
        text=True
    )

    # Extract the path from the last line of stdout
    path = Path(result.stdout.splitlines()[-1].strip().split(' ', 1)[1]) / 'profiles.yml'

    if path.exists():
        return path

    raise FileNotFoundError("Could not detect profiles.yml location.")
