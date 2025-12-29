"""Shared pytest fixtures for gstack tests."""

from __future__ import annotations

import os
import subprocess
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository with an initial commit.

    The repository is initialized with:
    - 'main' as the default branch
    - An initial commit with a README file
    - Working directory changed to the repo root

    Yields:
        Path to the temporary repository root.
    """
    original_cwd = os.getcwd()
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    os.chdir(repo_path)

    # Initialize git repo with 'main' as default branch
    subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        check=True,
        capture_output=True,
    )

    # Create initial commit
    readme = repo_path / "README.md"
    readme.write_text("# Test Repository\n")
    subprocess.run(["git", "add", "README.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        check=True,
        capture_output=True,
    )

    yield repo_path

    # Restore original working directory
    os.chdir(original_cwd)


@pytest.fixture
def temp_git_repo_with_remote(temp_git_repo: Path, tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repository with a bare remote.

    Extends temp_git_repo with:
    - A bare remote repository at tmp_path/remote.git
    - Remote 'origin' configured pointing to the bare repo
    - Initial push to origin/main

    Yields:
        Path to the temporary repository root (same as temp_git_repo).
    """
    # Create bare remote
    remote_path = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(remote_path)], check=True, capture_output=True)

    # Add remote and push
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote_path)],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        check=True,
        capture_output=True,
    )

    yield temp_git_repo


@pytest.fixture
def mock_subprocess(mocker: MockerFixture) -> MagicMock:
    """Mock subprocess.run for testing git/gh commands without side effects.

    Returns a MagicMock that can be configured to return specific outputs.

    Example:
        def test_something(mock_subprocess):
            mock_subprocess.return_value = CompletedProcess(
                args=["git", "status"],
                returncode=0,
                stdout="",
                stderr=""
            )
            # Your test code here
    """
    mock = mocker.patch("subprocess.run")
    # Default to successful empty output
    mock.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="",
        stderr="",
    )
    return mock


@pytest.fixture
def mock_gh(mocker: MockerFixture) -> MagicMock:
    """Mock gh CLI commands for testing GitHub operations.

    Returns a MagicMock specifically for gh commands, allowing git commands
    to pass through to the real subprocess.

    Example:
        def test_pr_creation(mock_gh, temp_git_repo):
            mock_gh.return_value = subprocess.CompletedProcess(
                args=["gh", "pr", "create"],
                returncode=0,
                stdout='{"url": "https://github.com/..."}',
                stderr=""
            )
    """
    original_run = subprocess.run

    def selective_mock(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if cmd and cmd[0] == "gh":
            return mock.return_value
        return original_run(*args, **kwargs)

    mock = mocker.patch("subprocess.run", side_effect=selective_mock)
    mock.return_value = subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout="{}",
        stderr="",
    )
    return mock


# Helper functions for tests


def create_branch(name: str, parent: Optional[str] = None) -> None:
    """Create a new git branch, optionally from a specific parent."""
    if parent:
        subprocess.run(["git", "checkout", parent], check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", name], check=True, capture_output=True)


def make_commit(message: str = "Test commit", filename: Optional[str] = None) -> str:
    """Create a commit with an optional specific filename.

    Returns the commit SHA.
    """
    if filename is None:
        # Generate unique filename
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


def get_current_branch() -> str:
    """Get the current branch name."""
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()
