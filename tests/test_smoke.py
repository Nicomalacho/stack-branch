"""Smoke tests to verify test infrastructure works."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


def create_branch(name: str, parent: Optional[str] = None) -> None:
    """Create a new git branch, optionally from a specific parent."""
    if parent:
        subprocess.run(["git", "checkout", parent], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", name], check=True, capture_output=True)


def get_current_branch() -> str:
    """Get the current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def make_commit(message: str = "Test commit") -> str:
    """Create a commit and return the SHA."""
    import time

    filename = f"file_{time.time_ns()}.txt"
    Path(filename).write_text(f"Content for {message}\n")
    subprocess.run(["git", "add", filename], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_temp_git_repo_fixture(temp_git_repo: Path) -> None:
    """Verify temp_git_repo fixture creates a valid git repository."""
    assert temp_git_repo.exists()
    assert (temp_git_repo / ".git").is_dir()
    assert (temp_git_repo / "README.md").exists()


def test_temp_git_repo_has_main_branch(temp_git_repo: Path) -> None:
    """Verify temp_git_repo starts on main branch."""
    assert get_current_branch() == "main"


def test_create_branch_helper(temp_git_repo: Path) -> None:
    """Verify create_branch helper works."""
    create_branch("feature-1")
    assert get_current_branch() == "feature-1"


def test_make_commit_helper(temp_git_repo: Path) -> None:
    """Verify make_commit helper creates a commit and returns SHA."""
    sha = make_commit("Test commit message")
    assert len(sha) == 40  # Full SHA length
    assert all(c in "0123456789abcdef" for c in sha)


def test_temp_git_repo_with_remote_fixture(temp_git_repo_with_remote: Path) -> None:
    """Verify temp_git_repo_with_remote has origin configured."""
    import subprocess

    result = subprocess.run(
        ["git", "remote", "-v"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "origin" in result.stdout
