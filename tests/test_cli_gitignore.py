import os
import sys
from pathlib import Path
import pytest
import subprocess

# Ensure src/ is on the Python path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dot.cli import app

def run_cli_in_dir(tmp_path, gitignore_content=None, expect_exit_code=0, input_response=None):
    """
    Helper to invoke the CLI inside an isolated temp git repo.

    We avoid patching subprocess.run globally so that git commands (rev-parse, etc.)
    still function. We patch dot.dot.dbt_command so dbt is never actually invoked,
    returning a harmless echo command instead.
    """
    from unittest.mock import patch
    import io

    # Initialize a git repository in tmp_path
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        os.system("git init")
    finally:
        os.chdir(old_cwd)

    # Setup .gitignore only if content provided
    gitignore_path = tmp_path / ".gitignore"
    if gitignore_content is not None:
        gitignore_path.write_text(gitignore_content, encoding="utf-8")

    # Setup dbt_project.yml
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test", encoding="utf-8")
    # Setup vars.yml
    (tmp_path / "vars.yml").write_text("default: {}", encoding="utf-8")

    # Patch sys.argv to simulate CLI arguments
    old_argv = sys.argv
    sys.argv = ["dot", "build"]

    # Change working directory
    old_cwd = os.getcwd()
    os.chdir(tmp_path)

    stdout = io.StringIO()
    stderr = io.StringIO()

    try:
        patches = [
            patch("dot.dot.dbt_command", return_value=[sys.executable, "-c", "print('mocked')"]),
        ]
        if input_response is not None:
            patches.append(patch("builtins.input", lambda _: input_response))

        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                try:
                    app()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)

    return exit_code, stdout.getvalue(), stderr.getvalue()


# Minimal ExitStack import (only when used to keep import locality clear)
from contextlib import ExitStack


def test_cli_refuses_without_gitignore(tmp_path, caplog):
    # .gitignore missing, should fail
    gitignore_path = tmp_path / ".gitignore"
    if gitignore_path.exists():
        gitignore_path.unlink()
    with caplog.at_level("ERROR"):
        exit_code, stdout, stderr = run_cli_in_dir(tmp_path, gitignore_content=None)
        assert any("No .gitignore found in the git repository root" in message for message in caplog.messages)


def test_cli_bypass_gitignore_check(tmp_path):
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text("", encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["dot", "--no-gitignore-check", "build"]
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    from unittest.mock import patch
    import io
    stdout = io.StringIO()
    try:
        with patch("sys.stdout", stdout):
            with patch("dot.dot.dbt_command", return_value=[sys.executable, "-c", "print('mocked')"]):
                try:
                    app()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
        output = stdout.getvalue()
        assert exit_code == 0
        assert "dbt_project_path" in output
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)


def test_cli_bypass_gitignore_check_with_bad_entry(tmp_path):
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text("# test\n", encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["dot", "--no-gitignore-check", "build"]
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    from unittest.mock import patch
    import io
    stdout = io.StringIO()
    try:
        with patch("sys.stdout", stdout):
            with patch("dot.dot.dbt_command", return_value=[sys.executable, "-c", "print('mocked')"]):
                try:
                    app()
                    exit_code = 0
                except SystemExit as e:
                    exit_code = e.code
        output = stdout.getvalue()
        assert exit_code == 0
        assert "dbt_project_path" in output
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)


def test_cli_accepts_with_dot_entry(tmp_path):
    result = run_cli_in_dir(tmp_path, gitignore_content=".dot/\n")
    exit_code, stdout, stderr = result
    assert exit_code == 0
    assert "dbt_project_path" in stdout


def test_cli_offers_to_insert_dot_entry(tmp_path, monkeypatch):
    responses = iter(["y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    result = run_cli_in_dir(tmp_path, gitignore_content="# test\n")
    exit_code, stdout, stderr = result
    gitignore_path = tmp_path / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".dot/" in content
    assert "Added '.dot/' to .gitignore." in stdout or "Added '.dot/' to .gitignore." in stderr
    assert exit_code == 0


def test_cli_refuses_without_dot_entry(tmp_path):
    result = run_cli_in_dir(tmp_path, gitignore_content="# test\n", input_response="n")
    exit_code, stdout, stderr = result
    assert "Refusing to run: '.dot/' must be ignored in .gitignore for this CLI to operate." in stderr
    assert exit_code == 1


def test_cli_offers_to_insert_dot_entry(tmp_path, monkeypatch):
    responses = iter(["y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    exit_code, stdout, stderr = run_cli_in_dir(tmp_path, gitignore_content="# test\n")
    gitignore_path = tmp_path / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".dot/" in content
    assert "Added '.dot/' to .gitignore." in stdout or "Added '.dot/' to .gitignore." in stderr


def test_cli_bypass_gitignore_check(tmp_path):
    # Should not fail even if .gitignore is missing
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        os.system("git init")
    finally:
        os.chdir(old_cwd)
    gitignore_path = tmp_path / ".gitignore"
    if gitignore_path.exists():
        gitignore_path.unlink()
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test", encoding="utf-8")
    (tmp_path / "vars.yml").write_text("default: {}", encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["dot", "--no-gitignore-check", "build"]
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        try:
            app()
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code
        assert exit_code == 0
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)


def test_cli_bypass_gitignore_check_with_bad_entry(tmp_path):
    # Should not fail even if .gitignore does not contain .dot/
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        os.system("git init")
    finally:
        os.chdir(old_cwd)
    gitignore_path = tmp_path / ".gitignore"
    gitignore_path.write_text("# test\n", encoding="utf-8")
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test", encoding="utf-8")
    (tmp_path / "vars.yml").write_text("default: {}", encoding="utf-8")
    old_argv = sys.argv
    sys.argv = ["dot", "--no-gitignore-check", "build"]
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        try:
            app()
            exit_code = 0
        except SystemExit as e:
            exit_code = e.code
        assert exit_code == 0
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)


def test_cli_refuses_without_dot_entry(tmp_path):
    result = run_cli_in_dir(tmp_path, gitignore_content="# test\n", expect_exit_code=1, input_response="n")
    exit_code, stdout, stderr = result
    assert exit_code == 1


def test_cli_accepts_with_dot_entry(tmp_path):
    result = run_cli_in_dir(tmp_path, gitignore_content=".dot/\n", expect_exit_code=0)
    exit_code, stdout, stderr = result
    assert exit_code == 0


def test_cli_offers_to_insert_dot_entry(tmp_path, monkeypatch):
    responses = iter(["y"])
    monkeypatch.setattr("builtins.input", lambda _: next(responses))
    result = run_cli_in_dir(tmp_path, gitignore_content="# test\n", expect_exit_code=0)
    exit_code, stdout, stderr = result
    gitignore_path = tmp_path / ".gitignore"
    content = gitignore_path.read_text(encoding="utf-8")
    assert ".dot/" in content
    assert exit_code == 0
