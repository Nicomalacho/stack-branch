"""Git operations wrapper for gstack.

All git commands are executed via subprocess, capturing output for error handling.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from gstack.exceptions import DirtyWorkdirError, GitError, NotAGitRepoError


@dataclass
class GitResult:
    """Result of a git command execution."""

    stdout: str
    stderr: str
    returncode: int


def run_git(*args: str, check: bool = True, cwd: Optional[Path] = None) -> GitResult:
    """Run a git command and return the result.

    Args:
        *args: Git command arguments (e.g., "status", "--porcelain").
        check: If True, raise GitError on non-zero exit code.
        cwd: Working directory for the command.

    Returns:
        GitResult with stdout, stderr, and returncode.

    Raises:
        GitError: If check=True and command fails.
    """
    cmd = ["git", *args]

    # Set environment to prevent git from opening an editor
    env = os.environ.copy()
    env["GIT_EDITOR"] = "true"

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=env,
    )

    git_result = GitResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )

    if check and result.returncode != 0:
        error_msg = (
            result.stderr.strip() or result.stdout.strip() or f"Git command failed: {' '.join(cmd)}"
        )
        raise GitError(error_msg, returncode=result.returncode, stderr=result.stderr)

    return git_result


def get_current_branch() -> str:
    """Get the name of the current branch.

    Returns:
        The current branch name.

    Raises:
        GitError: If not on a branch (detached HEAD) or other git error.
    """
    result = run_git("rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip()


def is_workdir_clean() -> bool:
    """Check if the working directory is clean (no uncommitted changes).

    Returns:
        True if clean, False if there are uncommitted changes.
    """
    result = run_git("status", "--porcelain")
    return len(result.stdout.strip()) == 0


def require_clean_workdir() -> None:
    """Require the working directory to be clean.

    Raises:
        DirtyWorkdirError: If there are uncommitted changes.
    """
    if not is_workdir_clean():
        raise DirtyWorkdirError()


def detect_trunk() -> str:
    """Auto-detect the trunk branch (main or master).

    Returns:
        'main' if it exists, otherwise 'master'.

    Raises:
        GitError: If neither main nor master exists.
    """
    if branch_exists("main"):
        return "main"
    if branch_exists("master"):
        return "master"
    raise GitError("Could not detect trunk branch. Neither 'main' nor 'master' exists.")


def checkout_branch(name: str, create: bool = False) -> None:
    """Switch to a branch, optionally creating it.

    Args:
        name: Branch name to checkout.
        create: If True, create the branch if it doesn't exist.

    Raises:
        GitError: If checkout fails.
    """
    if create:
        run_git("checkout", "-b", name)
    else:
        run_git("checkout", name)


def branch_exists(name: str) -> bool:
    """Check if a branch exists.

    Args:
        name: Branch name to check.

    Returns:
        True if the branch exists, False otherwise.
    """
    result = run_git("rev-parse", "--verify", f"refs/heads/{name}", check=False)
    return result.returncode == 0


def is_ancestor(commit_a: str, commit_b: str) -> bool:
    """Check if commit_a is an ancestor of commit_b.

    Args:
        commit_a: The potential ancestor commit.
        commit_b: The potential descendant commit.

    Returns:
        True if commit_a is an ancestor of commit_b.
    """
    result = run_git("merge-base", "--is-ancestor", commit_a, commit_b, check=False)
    return result.returncode == 0


def rebase(
    target: str,
    onto: Optional[str] = None,
    upstream: Optional[str] = None,
    check: bool = True,
) -> GitResult:
    """Rebase the current branch.

    Args:
        target: The branch to rebase onto (used as upstream if onto not specified).
        onto: For --onto rebases, the new base.
        upstream: For --onto rebases, the upstream to replay commits from.
        check: If True, raise GitError on failure.

    Returns:
        GitResult from the rebase command.

    Raises:
        GitError: If check=True and rebase fails (e.g., conflicts).
    """
    if onto is not None and upstream is not None:
        # git rebase --onto <onto> <upstream>
        return run_git("rebase", "--onto", onto, upstream, check=check)
    else:
        # Simple rebase
        return run_git("rebase", target, check=check)


def is_rebase_in_progress() -> bool:
    """Check if a rebase is currently in progress.

    Returns:
        True if a rebase is in progress.
    """
    try:
        repo_root = get_repo_root()
    except NotAGitRepoError:
        return False

    git_dir = repo_root / ".git"

    # Check for rebase-merge (interactive rebase) or rebase-apply (regular rebase)
    return (git_dir / "rebase-merge").exists() or (git_dir / "rebase-apply").exists()


def rebase_continue() -> GitResult:
    """Continue a paused rebase after resolving conflicts.

    Returns:
        GitResult from the rebase --continue command.

    Raises:
        GitError: If there's no rebase in progress or conflicts remain.
    """
    return run_git("rebase", "--continue")


def rebase_abort() -> GitResult:
    """Abort the current rebase operation.

    Returns:
        GitResult from the rebase --abort command.

    Raises:
        GitError: If there's no rebase to abort.
    """
    return run_git("rebase", "--abort")


def fetch(remote: str, branch: str) -> GitResult:
    """Fetch a branch from a remote.

    Args:
        remote: Remote name (e.g., 'origin').
        branch: Branch name to fetch.

    Returns:
        GitResult from the fetch command.
    """
    return run_git("fetch", remote, branch)


def push(
    remote: str,
    branch: str,
    force_with_lease: bool = True,
    set_upstream: bool = False,
) -> GitResult:
    """Push a branch to a remote.

    Args:
        remote: Remote name (e.g., 'origin').
        branch: Branch name to push.
        force_with_lease: Use --force-with-lease for safe force push.
        set_upstream: Set upstream tracking (-u flag).

    Returns:
        GitResult from the push command.
    """
    args = ["push"]

    if set_upstream:
        args.append("-u")

    if force_with_lease:
        args.append("--force-with-lease")

    args.extend([remote, branch])

    return run_git(*args)


def get_repo_root() -> Path:
    """Get the root directory of the current git repository.

    Returns:
        Path to the repository root.

    Raises:
        NotAGitRepoError: If not inside a git repository.
    """
    result = run_git("rev-parse", "--show-toplevel", check=False)

    if result.returncode != 0:
        raise NotAGitRepoError()

    return Path(result.stdout.strip())


def delete_branch(name: str, force: bool = False) -> GitResult:
    """Delete a local branch.

    Args:
        name: Branch name to delete.
        force: If True, force delete even if not fully merged.

    Returns:
        GitResult from the branch delete command.

    Raises:
        GitError: If deletion fails.
    """
    flag = "-D" if force else "-d"
    return run_git("branch", flag, name)


def squash_commits(parent: str) -> GitResult:
    """Squash all commits on the current branch since parent into one.

    This is useful before rebasing to reduce the number of potential conflicts.
    If there's only one commit (or no commits), this is a no-op.

    Args:
        parent: The parent branch/commit to squash commits since.

    Returns:
        GitResult from the final operation (or empty result if no-op).
    """
    # Get commit count between parent and HEAD
    result = run_git("rev-list", "--count", f"{parent}..HEAD")
    count = int(result.stdout.strip())

    if count <= 1:
        # Nothing to squash
        return GitResult(stdout="", stderr="", returncode=0)

    # Get the first commit message (the one right after parent)
    # We use reverse to get commits in chronological order, then take the first
    msg_result = run_git("log", "--format=%B", "--reverse", f"{parent}..HEAD")
    messages = msg_result.stdout.strip().split("\n\n")
    first_message = messages[0].strip() if messages else f"Squashed {count} commits"

    # Soft reset to parent, keeping all changes staged
    run_git("reset", "--soft", parent)

    # Create single squashed commit with the first commit's message
    return run_git("commit", "-m", first_message)
