import os
import sys
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch
import io
import json
import pytest

# Ensure src/ is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dot.cli import app

def _init_git_repo(tmp_path: Path):
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        os.system("git init -q")
    finally:
        os.chdir(old_cwd)

def _write_dbt_project(tmp_path: Path):
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test\n", encoding="utf-8")

def _run_cli(tmp_path: Path, argv, input_responses=None):
    """
    Run the CLI inside tmp_path, patching dbt_command to avoid real dbt execution.
    input_responses: iterable of responses (strings) for successive prompts.
    Returns (exit_code, stdout, stderr)
    """
    _init_git_repo(tmp_path)
    _write_dbt_project(tmp_path)

    old_cwd = os.getcwd()
    old_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()

    sys.argv = ["dot", *argv]
    os.chdir(tmp_path)

    # Iterator for prompt responses
    if input_responses is not None:
        responses = iter(input_responses)
        def _fake_input(_):
            try:
                return next(responses)
            except StopIteration:
                return ""
    else:
        _fake_input = lambda _: ""

    with ExitStack() as stack:
        stack.enter_context(patch("dot.dot.dbt_command", return_value=[sys.executable, "-c", "print('mocked dbt')"]))
        stack.enter_context(patch("sys.stdin.isatty", lambda: True))
        stack.enter_context(patch("sys.stdout", stdout))
        stack.enter_context(patch("sys.stderr", stderr))
        stack.enter_context(patch("builtins.input", _fake_input))
        try:
            rc = app()
        except SystemExit as e:
            rc = e.code
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
    return rc, stdout.getvalue(), stderr.getvalue()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_gitignore_present_no_prompt(tmp_path):
    (tmp_path / ".gitignore").write_text(".dot/\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"])
    assert rc == 0
    # Prompt summary logged via logger; presence not asserted here
    assert ".dot/" in (tmp_path / ".gitignore").read_text(encoding="utf-8")

def test_gitignore_missing_file_never_disables(tmp_path):
    # No .gitignore at all; choose 'e' (never)
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["e"])
    assert rc == 0
    cfg = tmp_path / ".dot" / "config.yml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert "prompts:" in text
    assert "gitignore: disabled" in text

def test_gitignore_missing_entry_yes_adds(tmp_path):
    (tmp_path / ".gitignore").write_text("# initial\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".dot/" in content

def test_gitignore_missing_entry_no_aborts(tmp_path):
    (tmp_path / ".gitignore").write_text("# test\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["n"])
    assert rc == 1  # mandatory prompt abort
    # Ensure not modified
    content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert ".dot/" not in content

def test_gitignore_missing_entry_never_disables_and_continues(tmp_path):
    (tmp_path / ".gitignore").write_text("# test\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["e"])
    assert rc == 0
    cfg_text = (tmp_path / ".dot" / "config.yml").read_text(encoding="utf-8")
    assert "gitignore: disabled" in cfg_text
    # Second run should not prompt (supply no responses)
    rc2, out2, err2 = _run_cli(tmp_path, ["build"])
    assert rc2 == 0

def test_global_disable_skips_gitignore_enforcement(tmp_path):
    # No .gitignore but global disable
    rc, out, err = _run_cli(tmp_path, ["--disable-prompts", "build"])
    assert rc == 0
    # No config file produced (feature not prompted)
    assert not (tmp_path / ".dot" / "config.yml").exists()

def test_gitignore_yes_then_idempotent_second_run(tmp_path):
    (tmp_path / ".gitignore").write_text("# header\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    rc2, out2, err2 = _run_cli(tmp_path, ["build"])
    assert rc2 == 0
    # Ensure single entry (avoid duplicates)
    lines = [l.strip() for l in (tmp_path / ".gitignore").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines.count(".dot/") == 1
