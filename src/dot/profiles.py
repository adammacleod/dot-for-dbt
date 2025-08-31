import yaml
import subprocess
from pathlib import Path
from . import dot


def write_isolated_profiles_yml(
    dbt_project_path: Path,
    commit_hash: str,
    profiles_dir: Path,
    active_context: str,
) -> Path:
    """
    Write a dbt profiles.yml for an isolated schema build.

    Args:
        dbt_project_path (Path): The path to the dbt project directory.
        commit_hash (str): The full commit hash.
        profiles_dir (Path): Directory where profiles.yml will be written (e.g., .dot/<hash>/).
        active_context (str): The dbt context/target name to use.

    Returns:
        Path: The path to the written profiles.yml file.
    """
    short_hash = commit_hash[:8]

    # Open the existing profiles.yml and read it's contents
    profiles_yml_path = _profiles_yml_path(active_context)
    with open(profiles_yml_path, "r") as f:
        all_profiles = yaml.safe_load(f)

    # Get the profile name from dbt_project.yml
    with open(dbt_project_path / "dbt_project.yml", "r") as f:
        dbt_project = yaml.safe_load(f)
    profile_name = dbt_project.get("profile")

    # Get the profile from profiles.yml
    if profile_name not in all_profiles:
        raise ValueError(f"Profile '{profile_name}' not found in profiles.yml.")
    profile = all_profiles[profile_name]

    # Get the correct output configuration
    if not "outputs" in profile:
        raise ValueError(f"Profile '{profile_name}' does not have an 'outputs' section in {profiles_yml_path}")
    
    if not active_context in profile["outputs"]:
        raise ValueError(f"Target '{active_context}' not found in profile '{profile_name}' outputs.")

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
    
    profiles_path = profiles_dir / "profiles.yml"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    with open(profiles_path, "w") as f:
        yaml.safe_dump(new_profiles_yml, f, default_flow_style=False)
    
    return profiles_dir


def _profiles_yml_path(active_context: str) -> Path:
    """
    Detect the location of profiles.yml using dbt debug output.
    Returns:
        Path: The path to the detected profiles.yml file.
    """
    # Use dot.dbt_command to run dbt debug and capture output
    dbt_command = dot.dbt_command(
        dbt_command_name="debug",
        vars_yml_path=Path.cwd() / "vars.yml",
        active_context=active_context,
        passthrough_args=['--config-dir']
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