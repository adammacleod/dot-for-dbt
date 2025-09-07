import subprocess
from pathlib import Path


def _run_git(repo_path: Path, *args: str) -> str:
    """
    Run a git command in the specified repository and return stdout (stripped).

    Raises:
        RuntimeError: If the git command fails.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


def get_repo_path(path: Path) -> Path:
    """
    Return the git repository root containing `path` using:
        git rev-parse --show-toplevel

    Args:
        path (Path): A path within the repository.

    Returns:
        Path: Repository root.

    Raises:
        RuntimeError: If not inside a git repository.
    """
    try:
        repo_root = _run_git(path, "rev-parse", "--show-toplevel")
        return Path(repo_root)
    except Exception as e:
        raise RuntimeError(f"Could not determine git repository root for {path}: {e}")


def get_full_commit_hash(repo_path: Path, gitref: str) -> str:
    """
    Resolve a git ref to the full 40‑character commit hash.

    Args:
        repo_path (Path): Path to the repository root.
        gitref (str): A ref: branch, tag, full/short hash, reflog expr, etc.

    Returns:
        str: 40‑character commit hash.

    Raises:
        ValueError: If the ref cannot be resolved.
    """
    try:
        full_hash = _run_git(repo_path, "rev-parse", gitref)
    except Exception as e:
        raise ValueError(f"Could not resolve git ref '{gitref}': {e}")

    if len(full_hash) != 40:
        raise ValueError(f"Resolved hash for '{gitref}' is not 40 chars: {full_hash}")
    return full_hash


def get_short_commit_hash(repo_path: Path, gitref: str) -> str:
    """
    Resolve a git ref to its unique abbreviated commit hash (length chosen by git).

    Args:
        repo_path (Path): Path to the repository root.
        gitref (str): A ref: branch, tag, full/short hash, reflog expr, etc.

    Returns:
        str: Abbreviated commit hash (length >= 7, <= 40).
    """
    try:
        short_hash = _run_git(repo_path, "rev-parse", "--short", gitref)
    except Exception as e:
        raise ValueError(f"Could not resolve git ref '{gitref}': {e}")
    return short_hash


def create_worktree(
    repo_path: Path,
    worktree_path: Path,
    full_commit_hash: str,
) -> None:
    """
    Create a clean worktree at the specified full commit hash.

    If the worktree path already exists, this is a no-op.

    Args:
        repo_path (Path): Repository root.
        worktree_path (Path): Destination path for the worktree.
        full_commit_hash (str): 40‑character commit hash to check out.

    Raises:
        RuntimeError: If the worktree cannot be created.
    """
    if worktree_path.exists():
        return

    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", "--detach", str(worktree_path), full_commit_hash],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to add worktree for commit {full_commit_hash}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
