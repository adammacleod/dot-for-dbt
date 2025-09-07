import os
import sys
import pytest
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.dot.git import get_short_commit_hash, get_full_commit_hash

@pytest.mark.parametrize("ref", ["HEAD", "main"])
def test_get_full_commit_hash_various(ref: str):
    try:
        commit_hash = get_full_commit_hash(Path(os.getcwd()), ref)
        assert isinstance(commit_hash, str)
        assert len(commit_hash) == 40
        int(commit_hash, 16)
    except Exception:
        if ref == "main":
            pytest.skip("Branch 'main' does not exist in this repo")
        else:
            raise

@pytest.mark.parametrize("ref", ["HEAD", "main"])
def test_get_short_commit_hash_various(ref: str):
    try:
        short_hash = get_short_commit_hash(Path(os.getcwd()), ref)
        assert isinstance(short_hash, str)
        assert 7 <= len(short_hash) <= 40
        int(short_hash, 16)
    except Exception:
        if ref == "main":
            pytest.skip("Branch 'main' does not exist in this repo")
        else:
            raise
