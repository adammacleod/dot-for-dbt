import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dot.git import resolve_git_ref

@pytest.mark.parametrize("ref", ["HEAD", "main"])
def test_resolve_git_ref_various(ref: str):
    try:
        commit_hash = resolve_git_ref(ref, Path(os.getcwd()))
        assert isinstance(commit_hash, str)
        assert len(commit_hash) == 40
        int(commit_hash, 16)
    except Exception:
        # It's possible 'main' does not exist in all repos, so allow failure
        if ref == "main":
            pytest.skip("Branch 'main' does not exist in this repo")
        else:
            raise
