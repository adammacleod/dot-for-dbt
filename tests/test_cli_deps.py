import os
import sys
import io
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch, call
import pytest

# Ensure src/ on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dot.cli import app


def _init_git_repo_with_commit(tmp_path: Path):
    """
    Initialize a git repo and create an initial commit so that HEAD resolves.
    """
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        os.system("git init -q")
        # Configure user (required for commit in clean test envs)
        os.system('git config user.email "test@example.com"')
        os.system('git config user.name "Test User"')
        # Minimal file
        (tmp_path / "README.md").write_text("test\n", encoding="utf-8")
        os.system("git add README.md")
        os.system('git commit -q -m "init"')
    finally:
        os.chdir(old_cwd)


def _write_dbt_project(tmp_path: Path):
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test\n", encoding="utf-8")


def _write_environments(tmp_path: Path):
    (tmp_path / "dot_environments.yml").write_text(
        "environment:\n"
        "  default: dev\n"
        "  dev:\n"
        "    target: dev\n",
        encoding="utf-8"
    )


def _run_cli(tmp_path: Path, argv):
    """
    Run CLI inside tmp_path with patches capturing subprocess invocations.
    Returns (exit_code, subprocess_calls)
    """
    _init_git_repo_with_commit(tmp_path)
    _write_dbt_project(tmp_path)
    _write_environments(tmp_path)

    old_cwd = os.getcwd()
    old_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()
    sys.argv = ["dot", *argv]
    os.chdir(tmp_path)

    recorded_dbt_command_calls = []

    def _fake_dbt_command(dbt_command_name: str, **kwargs):
        # Record which logical dbt command was requested
        recorded_dbt_command_calls.append(dbt_command_name)
        # Return a sentinel "command" list that subprocess.run will "execute"
        return [sys.executable, "-c", f"print('{dbt_command_name} executed')"]

    with ExitStack() as stack:
        # Patch repo path detection to avoid real git subprocess calls
        stack.enter_context(patch("dot.cli.get_repo_path", return_value=tmp_path))
        stack.enter_context(patch("dot.dot.dbt_command", side_effect=_fake_dbt_command))
        mock_run = stack.enter_context(patch("subprocess.run"))
        # Simulate successful runs
        mock_run.return_value.returncode = 0
        stack.enter_context(patch("sys.stdout", stdout))
        stack.enter_context(patch("sys.stderr", stderr))
        try:
            rc = app()
        except SystemExit as e:
            rc = e.code
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)

    return rc, recorded_dbt_command_calls, [c.args[0] for c in mock_run.call_args_list], stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_isolated_build_runs_deps_first(tmp_path):
    rc, logical_calls, subprocess_cmds, out, err = _run_cli(tmp_path, ["build", "dev@HEAD"])
    assert rc == 0
    # The CLI builds the deps command first, and then issues build.
    assert logical_calls[0] == "deps"
    assert logical_calls[1] == "build"
    # Filter out non-dbt subprocess calls (e.g. git)
    dbt_calls = [c for c in subprocess_cmds if c and isinstance(c, list) and c[0] == sys.executable]
    assert len(dbt_calls) == 2
    assert "deps executed" in dbt_calls[0][-1]
    assert "build executed" in dbt_calls[1][-1]


def test_isolated_build_no_deps_flag_skips_deps(tmp_path):
    rc, logical_calls, subprocess_cmds, out, err = _run_cli(tmp_path, ["--no-deps", "build", "dev@HEAD"])
    assert rc == 0
    # Only the primary command should appear
    assert logical_calls == ["build"]
    dbt_calls = [c for c in subprocess_cmds if c and isinstance(c, list) and c[0] == sys.executable]
    assert len(dbt_calls) == 1
    assert "build executed" in dbt_calls[0][-1]


def test_isolated_build_primary_deps_not_double_run(tmp_path):
    rc, logical_calls, subprocess_cmds, out, err = _run_cli(tmp_path, ["deps", "dev@HEAD"])
    assert rc == 0
    # Should only run deps once (automatic deps suppressed because primary is deps)
    assert logical_calls == ["deps"]
    dbt_calls = [c for c in subprocess_cmds if c and isinstance(c, list) and c[0] == sys.executable]
    assert len(dbt_calls) == 1
    assert "deps executed" in dbt_calls[0][-1]


def test_non_isolated_build_no_auto_deps(tmp_path):
    # No @ref so not isolated
    rc, logical_calls, subprocess_cmds, out, err = _run_cli(tmp_path, ["build", "dev"])
    assert rc == 0
    assert logical_calls == ["build"]
    dbt_calls = [c for c in subprocess_cmds if c and isinstance(c, list) and c[0] == sys.executable]
    assert len(dbt_calls) == 1
    assert "build executed" in dbt_calls[0][-1]
