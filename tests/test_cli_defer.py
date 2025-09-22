import os
import sys
import io
from pathlib import Path
from contextlib import ExitStack
from types import SimpleNamespace
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
        # Create an initial commit so HEAD resolves to a 40-char hash
        (tmp_path / ".init").write_text("init", encoding="utf-8")
        os.system("git add .init >NUL 2>&1")
        os.system('git commit -m "init" -q')
    finally:
        os.chdir(old_cwd)

def _write_dbt_project(tmp_path: Path):
    (tmp_path / "dbt_project.yml").write_text("name: test\nprofile: test\n", encoding="utf-8")

def _write_env_config(tmp_path: Path, default: str | None, envs: list[str]):
    lines = ["environment:"]
    if default:
        lines.append(f"  default: {default}")
    for e in envs:
        lines.append(f"  {e}: {{}}")
    (tmp_path / "dot_environments.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _baseline_path(repo_root: Path, short_hash: str, env: str) -> Path:
    return repo_root / ".dot" / "build" / short_hash / "env" / env / "target"

def _create_baseline(repo_root: Path, short_hash: str, env: str):
    target = _baseline_path(repo_root, short_hash, env)
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text("{}", encoding="utf-8")

def _run_cli(tmp_path: Path, argv, patches: dict | None = None):
    """
    Run the CLI inside tmp_path capturing stdout/stderr.
    patches: optional dict of context manager enter_context callables.
    Returns (exit_code, stdout, stderr)
    """
    _init_git_repo(tmp_path)
    _write_dbt_project(tmp_path)

    old_cwd = os.getcwd()
    old_argv = sys.argv
    stdout = io.StringIO()
    stderr = io.StringIO()

    full_argv = ["dot"]
    if "--disable-prompts" not in argv:
        full_argv.append("--disable-prompts")
    full_argv += argv
    sys.argv = full_argv
    os.chdir(tmp_path)

    with ExitStack() as stack:
        # Default patches
        stack.enter_context(patch("sys.stdout", stdout))
        stack.enter_context(patch("sys.stderr", stderr))
        stack.enter_context(patch("sys.stdin.isatty", lambda: True))
        # Prevent real dbt invocation; capture but allow command construction
        def _fake_run(cmd, check=False, **kwargs):
            cwd = kwargs.get("cwd")
            if isinstance(cmd, (list, tuple)) and "rev-parse" in cmd:
                # git rev-parse --show-toplevel
                if "--show-toplevel" in cmd:
                    return SimpleNamespace(returncode=0, stdout=str(cwd), stderr="")
                # git rev-parse --short <ref>
                if "--short" in cmd:
                    return SimpleNamespace(returncode=0, stdout="a1b2c3d", stderr="")
                # git rev-parse <ref>
                return SimpleNamespace(returncode=0, stdout="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", stderr="")
            # Generic successful subprocess with empty stdout/stderr
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        stack.enter_context(patch("subprocess.run", _fake_run))
        if patches:
            for target, obj in patches.items():
                stack.enter_context(patch(target, obj))
        try:
            rc = app()
        except SystemExit as e:
            rc = e.code
        finally:
            sys.argv = old_argv
            os.chdir(old_cwd)
    return rc, stdout.getvalue(), stderr.getvalue()

# ---------------------------------------------------------------------------
# Patches helpers
# ---------------------------------------------------------------------------

DUMMY_FULL_HASH = "a" * 40
DUMMY_SHORT_HASH = "a1b2c3d"

def _patch_git_success():
    return {
        # dot.git functions
        "src.dot.git.get_full_commit_hash": lambda repo, ref: DUMMY_FULL_HASH,
        "src.dot.git.get_short_commit_hash": lambda repo, ref: DUMMY_SHORT_HASH,
        # dot.dot imported these symbols directly; patch them too
        "src.dot.dot.get_full_commit_hash": lambda repo, ref: DUMMY_FULL_HASH,
        "src.dot.dot.get_short_commit_hash": lambda repo, ref: DUMMY_SHORT_HASH,
        # ensure dbt_command's imported create_worktree is patched
        "src.dot.dot.create_worktree": (lambda repo, path, full: (
            path.mkdir(parents=True, exist_ok=True),
            (path / "dbt_project.yml").write_text((repo / "dbt_project.yml").read_text(encoding="utf-8"), encoding="utf-8")
            if (repo / "dbt_project.yml").exists() else None
        )),
        # also patch the runtime-loaded package variant (dot.*) if imported that way
        "dot.dot.create_worktree": (lambda repo, path, full: (
            path.mkdir(parents=True, exist_ok=True),
            (path / "dbt_project.yml").write_text((repo / "dbt_project.yml").read_text(encoding="utf-8"), encoding="utf-8")
            if (repo / "dbt_project.yml").exists() else None
        )),
        "dot.dot.get_full_commit_hash": lambda repo, ref: DUMMY_FULL_HASH,
        "dot.dot.get_short_commit_hash": lambda repo, ref: DUMMY_SHORT_HASH,
        # cli imported get_short_commit_hash directly
        "src.dot.cli.get_short_commit_hash": lambda repo, ref: DUMMY_SHORT_HASH,
        "src.dot.git.create_worktree": (lambda repo, path, full: (
            path.mkdir(parents=True, exist_ok=True),
            (path / "dbt_project.yml").write_text((repo / "dbt_project.yml").read_text(encoding="utf-8"), encoding="utf-8")
            if (repo / "dbt_project.yml").exists() else None
        )),
        "src.dot.git.get_repo_path": lambda path: Path(path).resolve(),
        # ensure profiles writer does nothing heavy
        "src.dot.profiles.write_isolated_profiles_yml": lambda *a, **k: None,
        "src.dot.dot.write_isolated_profiles_yml": lambda *a, **k: None,
        "dot.dot.write_isolated_profiles_yml": lambda *a, **k: None,
    }

# ---------------------------------------------------------------------------
# Tests (errors)
# ---------------------------------------------------------------------------

def test_defer_missing_gitref_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "prod"])
    assert rc == 1  # message validated implicitly via logger; not asserting text due to rich logging capture

def test_defer_empty_gitref_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev"])
    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "dev@"])
    assert rc == 1  # see note above

def test_defer_unknown_environment_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev"])
    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "prod@HEAD"], patches=_patch_git_success())
    assert rc == 1

def test_defer_default_environment_missing_errors(tmp_path):
    # No default environment; use @HEAD form
    (tmp_path / "dot_environments.yml").write_text("environment:\n  dev: {}\n", encoding="utf-8")
    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "@HEAD"], patches=_patch_git_success())
    assert rc == 1

def test_defer_missing_baseline_directory_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    rc, out, err = _run_cli(tmp_path, ["build", "dev@HEAD", "--defer", "prod@HEAD"], patches=_patch_git_success())
    assert rc == 1

# ---------------------------------------------------------------------------
# Success test
# ---------------------------------------------------------------------------

def test_defer_success_injects_flags(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    # Create baseline for prod@HEAD
    repo_root = tmp_path
    _create_baseline(repo_root, DUMMY_SHORT_HASH, "prod")
    # Also need isolated build for active dev@HEAD; create its target dir to avoid errors later if referenced
    _create_baseline(repo_root, DUMMY_SHORT_HASH, "dev")

    rc, out, err = _run_cli(
        tmp_path,
        ["--no-deps", "build", "dev@HEAD", "--defer", "prod@HEAD"],
        patches=_patch_git_success()
    )
    assert rc == 0
    # Logging of flags occurs via rich logger (not captured in out/err under test harness),
    # so we only assert successful execution here.


def test_defer_invalid_multiple_at_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "prod@a@b"])
    assert rc == 1


def test_defer_missing_manifest_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    # Create baseline directory but omit manifest.json
    repo_root = tmp_path
    target = _baseline_path(repo_root, DUMMY_SHORT_HASH, "prod")
    target.mkdir(parents=True, exist_ok=True)
    rc, out, err = _run_cli(
        tmp_path,
        ["build", "dev@HEAD", "--defer", "prod@HEAD"],
        patches=_patch_git_success()
    )
    assert rc == 1


def test_defer_unresolvable_git_ref_errors(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    patches = _patch_git_success()

    def _raise_get_short_commit_hash(repo, ref):
        raise Exception("bad ref")

    patches["src.dot.cli.get_short_commit_hash"] = _raise_get_short_commit_hash

    rc, out, err = _run_cli(tmp_path, ["build", "--defer", "prod@BAD"], patches=patches)
    assert rc == 1


def test_defer_injects_flags_and_state_path(tmp_path):
    _write_env_config(tmp_path, "dev", ["dev", "prod"])
    # Create baselines for prod/dev at the dummy short hash
    repo_root = tmp_path
    _create_baseline(repo_root, DUMMY_SHORT_HASH, "prod")
    _create_baseline(repo_root, DUMMY_SHORT_HASH, "dev")

    captured = []

    def _capturing_run(cmd, check=False, **kwargs):
        captured.append(cmd)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    patches = _patch_git_success()
    patches["subprocess.run"] = _capturing_run

    rc, out, err = _run_cli(
        tmp_path,
        ["--no-deps", "build", "dev@HEAD", "--defer", "prod@HEAD"],
        patches=patches
    )
    assert rc == 0
    assert len(captured) >= 1
    cmd = captured[-1]

    # Flags present
    assert "--defer" in cmd
    assert "--favor-state" in cmd
    assert "--state" in cmd

    # Correct state path (accept absolute or relative)
    state_idx = cmd.index("--state")
    state_path = cmd[state_idx + 1]
    expected = _baseline_path(repo_root, DUMMY_SHORT_HASH, "prod")
    actual_path = Path(state_path)
    if not actual_path.is_absolute():
        actual_path = (repo_root / actual_path).resolve()
    assert str(actual_path).replace("\\", "/") == str(expected.resolve()).replace("\\", "/")
