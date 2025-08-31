from pathlib import Path
from pygit2 import Repository, Commit, Reference, discover_repository


def create_worktree(repo_path: Path, gitref: str) -> tuple[Path, str]:
    """
    Create a clean worktree at the specified commit hash in the given git repository.

    Args:
        repo_path (Path): Path to the git repository, or any directory within the repository.
        gitref (str): The git reference (branch, tag, or commit) to check out.

    Raises:
        ValueError: If the commit cannot be found or worktree cannot be created.
    """
    repo = Repository(discover_repository(str(repo_path)))

    commit, reference = resolve_git_ref(gitref, repo)
    if not commit:
        raise ValueError(f"Reference `{gitref}` not found in repository {repo_path}")

    # The working trees are always placed into .dot/commit_hash/worktree
    commit_hash_str = str(commit.id)
    worktree_path = Path(repo.workdir) / '.dot' / commit_hash_str / 'worktree'

    if repo.lookup_worktree(commit_hash_str) is not None:
        return worktree_path, commit_hash_str

    # Error if worktree directory already exists
    if worktree_path.exists():
        raise ValueError(f"Worktree directory already exists: {worktree_path}")
    
    worktree_path.parent.mkdir(parents=True, exist_ok=True)

    # Create the worktree
    if reference:
        repo.add_worktree(commit_hash_str, str(worktree_path), reference)
    else:
        repo.add_worktree(commit_hash_str, str(worktree_path))

    return worktree_path, commit_hash_str


def resolve_git_ref(ref: str, repo: Repository) -> tuple[Commit, Reference]:
    """
    Resolve a git ref (branch, tag, or hash) to a Commit object using pygit2.

    Args:
        ref (str): The git ref to resolve.
        repo (Repository): The git repository.

    Returns:
        Commit: The resolved commit.

    Raises:
        ValueError: If the ref cannot be resolved.
    """
    try:
        commit, reference = repo.resolve_refish(ref)
        return commit, reference
    except Exception as e:
        raise ValueError(f"Could not resolve git ref '{ref}': {e}")
