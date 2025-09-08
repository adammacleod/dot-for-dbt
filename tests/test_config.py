import sys
import pytest
import logging
import textwrap
from pathlib import Path

# Ensure src/ is on the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dot.config import (
    load_config,
    resolve_environment,
    dbt_cli_args,
    ConfigError,
    PROJECT_CONFIG_FILENAME,
    USER_CONFIG_FILENAME,
    PROJECT_VARIABLES_FILENAME,
)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def write(project_root: Path, name: str, content: str):
    p = project_root / name
    p.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
    return p

def minimal_dbt_project(tmp_path: Path):
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test\n", encoding="utf-8")

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

def test_load_config_no_files(tmp_path):
    minimal_dbt_project(tmp_path)
    cfg = load_config(tmp_path)
    assert cfg.variables == {}
    # raw_environments removed; project_environments & user_environments should both be empty
    assert cfg.project_environments == {}
    assert cfg.user_environments == {}
    env = resolve_environment(cfg, None)
    assert env.name is None
    assert env.args == {}
    assert env.vars == {}

def test_load_config_with_project_files_split(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          feature_flag:
            description: Test flag
            values: [true, false]
            strict: true
            required: true
        """
    )
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              feature_flag: true
          dev:
            target: dev
        """
    )
    cfg = load_config(tmp_path)
    assert "feature_flag" in cfg.variables
    assert cfg.default_environment == "dev"
    env = resolve_environment(cfg, None)
    assert env.name == "dev"
    assert env.args["target"] == "dev"
    assert env.vars["feature_flag"] is True

def test_user_config_merging(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            threads: 4
            vars:
              flag_a: false
          dev:
            target: dev
            vars:
              flag_a: true
        """
    )
    write(
        tmp_path,
        USER_CONFIG_FILENAME,
        """
        environment:
          all:
            threads: 8
          dev:
            target: dev_override
            vars:
              flag_b: 123
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, "dev")
    # threads overridden
    assert env.args["threads"] == 8
    # target overridden
    assert env.args["target"] == "dev_override"
    # vars merged (flag_a from project dev, flag_b from user config)
    assert env.vars["flag_a"] is True
    assert env.vars["flag_b"] == 123

def test_required_variable_missing_raises(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          must_set:
            required: true
        """
    )
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
        """
    )
    cfg = load_config(tmp_path)
    with pytest.raises(ConfigError) as exc:
        resolve_environment(cfg, "dev")
    assert "Required variable 'must_set'" in str(exc.value)

def test_required_variable_satisfied_via_all(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          must_set:
            required: true
        """
    )
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              must_set: 42
          dev:
            target: dev
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, "dev")
    assert env.vars["must_set"] == 42

def test_strict_variable_invalid_value(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          color:
            values: [red, blue]
            strict: true
        """
    )
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
            vars:
              color: green
        """
    )
    cfg = load_config(tmp_path)
    with pytest.raises(ConfigError) as exc:
        resolve_environment(cfg, "dev")
    assert "Variable 'color' has invalid value" in str(exc.value)

def test_environment_not_found_logs_detail(tmp_path, caplog):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
        """
    )
    with caplog.at_level(logging.DEBUG, logger="dot.config"):
        cfg = load_config(tmp_path)
        with pytest.raises(ConfigError) as exc:
            resolve_environment(cfg, "missing_env")

    assert "Environment 'missing_env' not found" in str(exc.value)
    # Ensure diagnostic info about presence of config files was logged
    assert any("Loading dot configuration for" in m for m in caplog.messages)

def test_dbt_cli_args_filtering(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
            select: my_model
            bogus: should_not_pass
            vars:
              example: 1
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, "dev")
    args = dbt_cli_args("run", env)
    # Allowed keys
    assert "target" in args
    assert "select" in args
    # Disallowed removed
    assert "bogus" not in args
    # Vars present
    assert args["vars"]["example"] == 1

def test_empty_environment_section(tmp_path):
    minimal_dbt_project(tmp_path)
    # Only variables file exists, no environments file.
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          something:
            required: false
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, None)
    assert env.name is None
    assert env.args == {}
    assert env.vars == {}

def test_user_config_adds_new_environment(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
        """
    )
    write(
        tmp_path,
        USER_CONFIG_FILENAME,
        """
        environment:
          staging:
            target: staging_target
        """
    )
    cfg = load_config(tmp_path)
    # new environment only defined in user config
    env = resolve_environment(cfg, "staging")
    assert env.name == "staging"
    assert env.args["target"] == "staging_target"


def test_environment_all_precedence_user(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              feature: 1
          dev:
            vars:
              feature: 2
        """
    )
    write(
        tmp_path,
        USER_CONFIG_FILENAME,
        """
        environment:
          all:
            vars:
              feature: 3
        """
    )
    cfg = load_config(tmp_path)
    # all from user config overrides all from project config
    env = resolve_environment(cfg, "dev")
    assert env.name == "dev"
    assert env.vars["feature"] == 3

def test_environment_all_precedence_user_specific(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              feature: 1
          dev:
            vars:
              feature: 2
        """
    )
    write(
        tmp_path,
        USER_CONFIG_FILENAME,
        """
        environment:
          all:
            vars:
              feature: 3
          dev:
            vars:
              feature: 4
        """
    )
    cfg = load_config(tmp_path)
    # Specific env in user config should take precedence over all
    env = resolve_environment(cfg, "dev")
    assert env.name == "dev"
    assert env.vars["feature"] == 4

def test_environment_vars_merge_precedence(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              feature: base
          dev:
            target: dev
            vars:
              feature: overridden
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, "dev")
    assert env.vars["feature"] == "overridden"

def test_required_variable_missing_in_specific_but_in_all_is_ok(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_VARIABLES_FILENAME,
        """
        vars:
          feature_flag:
            required: true
        """
    )
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          all:
            vars:
              feature_flag: true
          dev:
            target: dev
        """
    )
    cfg = load_config(tmp_path)
    env = resolve_environment(cfg, "dev")
    assert env.vars["feature_flag"] is True


def test_root_level_vars_in_environments_file_raises(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        vars:
          some_var:
            required: true
        environment:
          default: dev
          dev:
            target: dev
        """
    )
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path)
    assert "Root-level 'vars' found" in str(exc.value)


def test_root_level_vars_in_user_file_raises(tmp_path):
    minimal_dbt_project(tmp_path)
    write(
        tmp_path,
        PROJECT_CONFIG_FILENAME,
        """
        environment:
          default: dev
          dev:
            target: dev
        """
    )
    write(
        tmp_path,
        USER_CONFIG_FILENAME,
        """
        vars:
          some_var:
            required: true
        environment:
          dev:
            target: dev
        """
    )
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path)
    assert "Root-level 'vars' found" in str(exc.value)
