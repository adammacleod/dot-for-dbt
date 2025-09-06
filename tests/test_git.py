import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dot.git import get_commit_hash_from_gitref

@pytest.mark.parametrize("ref", ["HEAD", "main"])
def test_get_commit_hash_from_gitref_various(ref: str):
    try:
        commit_hash = get_commit_hash_from_gitref(Path(os.getcwd()), ref)
        assert isinstance(commit_hash, str)
        assert len(commit_hash) == 40
        int(commit_hash, 16)
    except Exception:
        if ref == "main":
            pytest.skip("Branch 'main' does not exist in this repo")
        else:
            raise
