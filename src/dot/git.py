import subprocess
from pathlib import Path
from pygit2 import Repository, discover_repository


def get_repo_path(path: Path) -> Path:
    """
    Find the root path of the git repository containing the given path.

    Args:
        path (Path): A path within the git repository.

    Returns:
        Path: The root path of the git repository.
    """

    return Path(_get_repo(path).workdir)


def _get_repo(path: Path) -> Repository:
    """
    Get the pygit2 Repository object for the given repository path.

    Args:
        path (Path): The path to the git repository.

    Returns:
        Repository: The pygit2 Repository object.

    Raises:
        ValueError: If the repository cannot be found.
    """
    repo = Repository(discover_repository(path))

    if not repo:
        raise ValueError(f"Could not find git repository at {path}")
    
    return repo


def get_commit_hash_from_gitref(
        repo_path: Path, 
        gitref: str
) -> str:
    repo = _get_repo(repo_path)

    try:
        commit, _ = repo.resolve_refish(gitref)
    except Exception as e:
        raise ValueError(f"Could not resolve git ref '{gitref}': {e}")

    if not commit:
        raise ValueError(f"Reference `{gitref}` not found in repository {repo_path}")

    commit_hash_str = str(commit.id)
    return commit_hash_str

def create_worktree(
    repo_path: Path, 
    worktree_path: Path,
    commit_hash: str
) -> None:
    """
    Create a clean worktree at the specified commit hash in the given git repository.

    Args:
        repo_path (Path): Path to the git repository.
        worktree_path (Path): Path to the worktree to create.
        commit_hash (str): The git reference (branch, tag, or commit) to check out.

    Raises:
        ValueError: If the commit cannot be found or worktree cannot be created.
    """

    # Return the worktree details if we previously checked it out.
    # TODO: Maybe update this in the future to check with git that the
    # worktree exists, and that it's a clean checkout.
    if worktree_path.exists():
        return
    
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), commit_hash],
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to add worktree: {result.stdout.strip()}")
