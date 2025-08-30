import pygit2
from pathlib import Path

def resolve_git_ref(ref: str, repo_path: Path) -> str:
    """
    Resolve a git ref (branch, tag, or hash) to a full commit hash using pygit2.

    Args:
        ref (str): The git ref to resolve.
        repo_path (Path): Path to the git repository.

    Returns:
        str: The full commit hash.

    Raises:
        ValueError: If the ref cannot be resolved.
    """
    repo = pygit2.Repository(pygit2.discover_repository(str(repo_path)))
    try:
        # Try as branch, tag, or commit
        obj = repo.revparse_single(ref)
        return str(obj.id)
    except Exception as e:
        raise ValueError(f"Could not resolve git ref '{ref}': {e}")
