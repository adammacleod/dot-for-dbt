import sys
import yaml
import pytest
from pathlib import Path

# Ensure src/ is on the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dot.profiles import write_isolated_profiles_yml

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

PROFILE_NAME = "test_profile"
ENVIRONMENT = "dev"

def make_dbt_project(tmp_path: Path):
    (tmp_path / "dbt_project.yml").write_text(f"name: example\nprofile: {PROFILE_NAME}\n", encoding="utf-8")

def write_profiles_file(tmp_path: Path, target_block: dict) -> Path:
    """
    Create a profiles.yml with a single profile + environment output.
    """
    profiles_content = {
        PROFILE_NAME: {
            "target": ENVIRONMENT,
            "outputs": {
                ENVIRONMENT: target_block
            }
        }
    }
    path = tmp_path / "profiles.yml"
    path.write_text(yaml.safe_dump(profiles_content), encoding="utf-8")
    return path

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_write_isolated_profiles_schema_only(tmp_path, monkeypatch):
    """
    When only 'schema' is present it should be suffixed with the short hash.
    """
    make_dbt_project(tmp_path)
    original_schema = "analytics"
    profiles_path = write_profiles_file(
        tmp_path,
        {
            "type": "postgres",
            "schema": original_schema,
            "threads": 4
        }
    )

    # Monkeypatch locator to return our temp profiles.yml
    monkeypatch.setattr("src.dot.profiles._profiles_yml_path", lambda *args, **kwargs: profiles_path)

    isolated_env_path = tmp_path / ".dot" / "build" / "dummy" / "env" / ENVIRONMENT
    short_hash = "abc1234"

    write_isolated_profiles_yml(
        dbt_project_path=tmp_path,
        isolated_dbt_project_path=tmp_path / "isolated_project",  # not used internally currently
        isolated_environment_path=isolated_env_path,
        short_hash=short_hash,
        active_environment=ENVIRONMENT,
    )

    new_profiles_file = isolated_env_path / "profiles.yml"
    assert new_profiles_file.exists()

    new_profiles = yaml.safe_load(new_profiles_file.read_text(encoding="utf-8"))
    target = new_profiles[PROFILE_NAME]["outputs"][ENVIRONMENT]
    assert target["schema"] == f"{original_schema}_{short_hash}"
    # Ensure unrelated keys preserved
    assert target["threads"] == 4
    assert "dataset" not in target

def test_write_isolated_profiles_dataset_only(tmp_path, monkeypatch):
    """
    When only 'dataset' is present it should behave like 'schema'.
    """
    make_dbt_project(tmp_path)
    original_dataset = "raw_layer"
    profiles_path = write_profiles_file(
        tmp_path,
        {
            "type": "bigquery",
            "dataset": original_dataset,
            "method": "oauth"
        }
    )

    monkeypatch.setattr("src.dot.profiles._profiles_yml_path", lambda *args, **kwargs: profiles_path)

    isolated_env_path = tmp_path / ".dot" / "build" / "dummy" / "env" / ENVIRONMENT
    short_hash = "fff9999"

    write_isolated_profiles_yml(
        dbt_project_path=tmp_path,
        isolated_dbt_project_path=tmp_path / "isolated_project",
        isolated_environment_path=isolated_env_path,
        short_hash=short_hash,
        active_environment=ENVIRONMENT,
    )

    new_profiles_file = isolated_env_path / "profiles.yml"
    assert new_profiles_file.exists()

    new_profiles = yaml.safe_load(new_profiles_file.read_text(encoding="utf-8"))
    target = new_profiles[PROFILE_NAME]["outputs"][ENVIRONMENT]
    assert target["dataset"] == f"{original_dataset}_{short_hash}"
    assert "schema" not in target

def test_write_isolated_profiles_both_schema_and_dataset_error(tmp_path, monkeypatch):
    """
    When both 'schema' and 'dataset' are present, raise ValueError.
    """
    make_dbt_project(tmp_path)
    profiles_path = write_profiles_file(
        tmp_path,
        {
            "type": "postgres",
            "schema": "foo",
            "dataset": "bar"
        }
    )

    monkeypatch.setattr("src.dot.profiles._profiles_yml_path", lambda *args, **kwargs: profiles_path)

    isolated_env_path = tmp_path / ".dot" / "build" / "dummy" / "env" / ENVIRONMENT

    with pytest.raises(ValueError) as exc:
        write_isolated_profiles_yml(
            dbt_project_path=tmp_path,
            isolated_dbt_project_path=tmp_path / "isolated_project",
            isolated_environment_path=isolated_env_path,
            short_hash="deadbee",
            active_environment=ENVIRONMENT,
        )

    assert "Both 'schema' and 'dataset' are set" in str(exc.value)
