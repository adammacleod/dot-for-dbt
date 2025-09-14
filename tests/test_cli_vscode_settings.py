import os
import sys
import io
from pathlib import Path
from contextlib import ExitStack
from unittest.mock import patch

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


def _run_cli(tmp_path: Path, argv, input_responses=None, patch_isatty: bool = True):
    """
    Run the CLI inside tmp_path, patching dbt_command to avoid real dbt execution.
    Returns (exit_code, stdout, stderr).
    If patch_isatty is not None, sys.stdin.isatty will be patched to return that value.
    """
    _init_git_repo(tmp_path)
    _write_dbt_project(tmp_path)

    # Ensure gitignore already compliant so only VSCode prompt (if any) triggers
    (tmp_path / ".gitignore").write_text(".dot/\n", encoding="utf-8")

    old_cwd = os.getcwd()
    old_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()

    sys.argv = ["dot", *argv]
    os.chdir(tmp_path)

    # Iterator for prompt responses (only VSCode prompt expected)
    if input_responses is not None:
        responses = iter(input_responses)

        def _fake_input(_):
            try:
                return next(responses)
            except StopIteration:
                return ""
    else:
        _fake_input = lambda _: ""

    patches = [
        patch("dot.dot.dbt_command", return_value=[sys.executable, "-c", "print('mocked dbt')"]),
        patch("sys.stdout", stdout),
        patch("sys.stderr", stderr),
        patch("builtins.input", _fake_input),
    ]
    # Force interactive by default so prompts execute during tests
    patches.append(patch("sys.stdin.isatty", lambda: patch_isatty))

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        try:
            rc = app()
        except SystemExit as e:
            rc = e.code
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
    return rc, stdout.getvalue(), stderr.getvalue()


# ---------------------------------------------------------------------------
# Helpers for assertions
# ---------------------------------------------------------------------------

def _load_json(path: Path):
    import json
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_vscode_settings_created_when_missing(tmp_path):
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    settings_path = tmp_path / ".vscode" / "settings.json"
    assert settings_path.exists()
    data = _load_json(settings_path)
    assert data["search.exclude"]["**/.dot"] is True
    assert data["search.exclude"]["**/.dot/**"] is True
    assert data["files.watcherExclude"]["**/.dot/**"] is True


def test_vscode_settings_declined_no_file(tmp_path):
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["n"])
    assert rc == 0  # Not mandatory
    settings_path = tmp_path / ".vscode" / "settings.json"
    assert not settings_path.exists()


def test_vscode_settings_never_disables(tmp_path):
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["e"])
    assert rc == 0
    cfg = tmp_path / ".dot" / "config.yml"
    assert cfg.exists()
    text = cfg.read_text(encoding="utf-8")
    assert "vscode: disabled" in text
    # Second run should not prompt (no responses) and not create file
    rc2, out2, err2 = _run_cli(tmp_path, ["build"])
    assert rc2 == 0
    assert not (tmp_path / ".vscode" / "settings.json").exists()


def test_vscode_partial_merge(tmp_path):
    # Pre-create partial settings (only one exclusion)
    settings_dir = tmp_path / ".vscode"
    settings_dir.mkdir(parents=True, exist_ok=True)
    partial = {
        "search.exclude": {"**/.dot": True},
        "files.watcherExclude": {},
    }
    import json
    (settings_dir / "settings.json").write_text(json.dumps(partial, indent=2), encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    data = _load_json(settings_dir / "settings.json")
    # All required keys present
    assert data["search.exclude"]["**/.dot"] is True
    assert data["search.exclude"]["**/.dot/**"] is True
    assert data["files.watcherExclude"]["**/.dot/**"] is True


def test_vscode_already_compliant_no_prompt(tmp_path):
    settings_dir = tmp_path / ".vscode"
    settings_dir.mkdir(parents=True, exist_ok=True)
    compliant = {
        "search.exclude": {"**/.dot": True, "**/.dot/**": True},
        "files.watcherExclude": {"**/.dot/**": True},
    }
    import json
    (settings_dir / "settings.json").write_text(json.dumps(compliant, indent=2), encoding="utf-8")
    # No responses provided; should still succeed and not modify
    rc, out, err = _run_cli(tmp_path, ["build"])
    assert rc == 0
    data = _load_json(settings_dir / "settings.json")
    assert data == compliant


def test_vscode_invalid_json_manual_instructions(tmp_path):
    settings_dir = tmp_path / ".vscode"
    settings_dir.mkdir(parents=True, exist_ok=True)
    # JSONC style (comment) => parse error
    invalid = '{\n  // comment\n  "search.exclude": {}\n}\n'
    (settings_dir / "settings.json").write_text(invalid, encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    # File should be unchanged
    assert (settings_dir / "settings.json").read_text(encoding="utf-8") == invalid
    # Should contain manual instructions snippet (look for '**/.dot' as marker)
    assert "**/.dot" in out or "**/.dot" in err


def test_vscode_global_disable(tmp_path):
    rc, out, err = _run_cli(tmp_path, ["--disable-prompts", "build"])
    assert rc == 0
    assert not (tmp_path / ".vscode").exists()
    # No config persisted because nothing prompted
    assert not (tmp_path / ".dot" / "config.yml").exists()


def test_vscode_non_interactive_skips(tmp_path):
    # When non-interactive (isatty False) prompts globally disabled; no file created
    rc, out, err = _run_cli(tmp_path, ["build"], patch_isatty=False)
    assert rc == 0
    assert not (tmp_path / ".vscode").exists()


def test_vscode_yes_then_idempotent_second_run(tmp_path):
    rc, out, err = _run_cli(tmp_path, ["build"], input_responses=["y"])
    assert rc == 0
    first_content = (tmp_path / ".vscode" / "settings.json").read_text(encoding="utf-8")
    rc2, out2, err2 = _run_cli(tmp_path, ["build"])
    assert rc2 == 0
    second_content = (tmp_path / ".vscode" / "settings.json").read_text(encoding="utf-8")
    assert first_content == second_content
